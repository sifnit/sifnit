#!/usr/bin/env python3
"""Lightweight point-of-sale server.

Standard library only: HTTPS server, JSON API and SQLite database.
Run:  python3 server.py --port 8443
"""
import argparse
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.environ.get("POS_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "pos.db")

SESSION_HOURS = 12
MAX_LOGIN_FAILS = 5
LOCKOUT_SECONDS = 60

DEFAULT_SETTINGS = {
    "shop_name": "Demo Shop",
    "abn": "",
    "address": "",
    "phone": "",
    "receipt_footer": "Thank you for shopping with us!",
    "timezone": "Australia/Sydney",
    "receipt_width_mm": "80",
    "low_stock_default": "3",
    "tag_base_url": "",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'cashier')),
    pin_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    vendor_code TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    price_cents INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 0,
    gst_free INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL DEFAULT 'sale' CHECK (kind IN ('sale', 'refund')),
    refund_of INTEGER REFERENCES sales(id),
    refunded_by INTEGER REFERENCES sales(id),
    subtotal_cents INTEGER NOT NULL,
    gst_cents INTEGER NOT NULL,
    rounding_cents INTEGER NOT NULL DEFAULT 0,
    total_cents INTEGER NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('cash', 'card', 'split')),
    cash_cents INTEGER NOT NULL DEFAULT 0,
    card_cents INTEGER NOT NULL DEFAULT 0,
    tendered_cents INTEGER NOT NULL DEFAULT 0,
    change_cents INTEGER NOT NULL DEFAULT 0,
    card_ref TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    product_id INTEGER REFERENCES products(id),
    sku TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    line_total_cents INTEGER NOT NULL,
    gst_cents INTEGER NOT NULL,
    cost_cents INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS stock_moves (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty_change INTEGER NOT NULL,
    reason TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    user_id INTEGER REFERENCES users(id),
    sale_id INTEGER REFERENCES sales(id)
);
CREATE TABLE IF NOT EXISTS cash_ups (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    float_cents INTEGER NOT NULL,
    expected_cents INTEGER NOT NULL,
    counted_cents INTEGER NOT NULL,
    diff_cents INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_moves_product ON stock_moves(product_id);
"""

SKU_RE = re.compile(r"^[A-Z0-9-]{1,16}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RawResponse:
    def __init__(self, body, ctype, filename=None):
        self.body, self.ctype, self.filename = body, ctype, filename


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------- helpers

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_pin(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 200_000).hex()


def round_cash(cents):
    """Round to the nearest 5c (Australian cash rounding)."""
    sign = -1 if cents < 0 else 1
    return sign * (((abs(cents) + 2) // 5) * 5)


def gst_of(cents):
    """GST contained in a GST-inclusive amount (1/11th)."""
    sign = -1 if cents < 0 else 1
    return sign * ((abs(cents) + 5) // 11)


def parse_scan(code):
    """Tag QR codes hold 'SKU|VENDOR|PRICE', or a link '<base>/t?c=SKU|VENDOR|PRICE'
    so a phone's own camera app opens the stocktake screen. Plain SKUs work too."""
    code = str(code).strip()
    if code.lower().startswith(("http://", "https://")):
        code = parse_qs(urlparse(code).query).get("c", [""])[0]
    parts = code.split("|")
    sku = parts[0].strip().upper()
    tag_price = None
    if len(parts) >= 3:
        try:
            tag_price = round(float(parts[2]) * 100)
        except ValueError:
            tag_price = None
    return sku, tag_price


def get_settings(conn):
    s = dict(DEFAULT_SETTINGS)
    s.update({r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")})
    return s


def now_local(conn=None):
    tzname = DEFAULT_SETTINGS["timezone"]
    if conn is not None:
        row = conn.execute("SELECT value FROM settings WHERE key='timezone'").fetchone()
        if row:
            tzname = row["value"]
    if ZoneInfo:
        try:
            return dt.datetime.now(ZoneInfo(tzname)).replace(tzinfo=None)
        except Exception:
            pass
    return dt.datetime.now()


def ts(conn):
    return now_local(conn).strftime("%Y-%m-%d %H:%M:%S")


def audit(conn, user_id, action, detail=""):
    conn.execute(
        "INSERT INTO audit_log (created_at, user_id, action, detail) VALUES (?,?,?,?)",
        (ts(conn), user_id, action, detail),
    )


def req_int(data, key, minimum=None, maximum=None, default=None):
    val = data.get(key, default)
    if val is None:
        raise ApiError(400, f"{key} is required")
    try:
        val = int(val)
    except (TypeError, ValueError):
        raise ApiError(400, f"{key} must be a whole number")
    if minimum is not None and val < minimum:
        raise ApiError(400, f"{key} must be at least {minimum}")
    if maximum is not None and val > maximum:
        raise ApiError(400, f"{key} must be at most {maximum}")
    return val


def req_str(data, key, maxlen, required=True, default=""):
    val = data.get(key, default)
    val = "" if val is None else str(val).strip()
    if required and not val:
        raise ApiError(400, f"{key} is required")
    if len(val) > maxlen:
        raise ApiError(400, f"{key} is too long (max {maxlen})")
    return val


def day_range(q):
    frm = q.get("from") or ""
    to = q.get("to") or ""
    if not DATE_RE.match(frm) or not DATE_RE.match(to):
        raise ApiError(400, "from and to must be YYYY-MM-DD")
    end = (dt.date.fromisoformat(to) + dt.timedelta(days=1)).isoformat()
    return frm + " 00:00:00", end + " 00:00:00"


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = connect()
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        salt = secrets.token_hex(16)
        conn.execute(
            "INSERT INTO users (name, role, pin_hash, salt) VALUES (?,?,?,?)",
            ("Owner", "owner", hash_pin("1234", salt), salt),
        )
        print("Created default user 'Owner' with PIN 1234 - change it in Settings.")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- sales logic

def build_sale(conn, items_in, payment):
    """Validate a cart and payment; prices for catalogue items come from the DB."""
    if not isinstance(items_in, list) or not items_in:
        raise ApiError(400, "Cart is empty")
    if len(items_in) > 200:
        raise ApiError(400, "Too many lines")
    lines = []
    for it in items_in:
        if not isinstance(it, dict):
            raise ApiError(400, "Bad cart line")
        qty = req_int(it, "qty", 1, 999)
        pid = it.get("product_id")
        if pid is not None:
            p = conn.execute(
                "SELECT * FROM products WHERE id=? AND active=1", (int(pid),)
            ).fetchone()
            if not p:
                raise ApiError(400, "Product no longer exists")
            unit = p["price_cents"]
            name, sku, gst_free, cost = p["name"], p["sku"], p["gst_free"], p["cost_cents"]
        else:
            name = req_str(it, "name", 60, default="Misc item") or "Misc item"
            unit = req_int(it, "price_cents", 1, 10_000_00)
            sku, gst_free, cost = "", 1 if it.get("gst_free") else 0, 0
            pid = None
        line_total = unit * qty
        lines.append({
            "product_id": pid, "sku": sku, "name": name, "qty": qty,
            "unit_price_cents": unit, "line_total_cents": line_total,
            "gst_cents": 0 if gst_free else gst_of(line_total), "cost_cents": cost,
        })
    subtotal = sum(l["line_total_cents"] for l in lines)
    gst = sum(l["gst_cents"] for l in lines)

    if not isinstance(payment, dict):
        raise ApiError(400, "Payment details missing")
    method = payment.get("method")
    if method == "card":
        card, cash_due = subtotal, 0
    elif method == "cash":
        card, cash_due = 0, round_cash(subtotal)
    elif method == "split":
        card = req_int(payment, "card_cents", 1, subtotal - 1)
        cash_due = round_cash(subtotal - card)
    else:
        raise ApiError(400, "Choose cash, card or split")
    rounding = card + cash_due - subtotal
    tendered = change = 0
    if cash_due:
        tendered = req_int(payment, "tendered_cents", 0, 100_000_00)
        if tendered < cash_due:
            raise ApiError(400, "Cash tendered is less than the amount due")
        change = tendered - cash_due
    card_ref = req_str(payment, "card_ref", 40, required=False)
    return lines, {
        "subtotal_cents": subtotal, "gst_cents": gst, "rounding_cents": rounding,
        "total_cents": subtotal + rounding, "payment_method": method,
        "cash_cents": cash_due, "card_cents": card, "tendered_cents": tendered,
        "change_cents": change, "card_ref": card_ref,
    }


def sale_detail(conn, sale_id):
    s = conn.execute(
        "SELECT s.*, u.name AS cashier FROM sales s JOIN users u ON u.id = s.user_id WHERE s.id=?",
        (sale_id,),
    ).fetchone()
    if not s:
        raise ApiError(404, "Sale not found")
    out = dict(s)
    out["items"] = [dict(r) for r in conn.execute(
        "SELECT * FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,))]
    return out


# ---------------------------------------------------------------- HTTP handler

login_fails = {}
login_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "POS/1.0"
    timeout = 30
    routes = []

    def log_message(self, fmt, *args):  # quieter logs
        if os.environ.get("POS_QUIET"):
            return
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # -- plumbing
    def send_json(self, status, obj, headers=None):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.security_headers()
        self.end_headers()

    def send_raw(self, r):
        self.send_response(200)
        self.send_header("Content-Type", r.ctype)
        self.send_header("Content-Length", str(len(r.body)))
        self.send_header("Cache-Control", "no-store")
        if r.filename:
            self.send_header("Content-Disposition", f'attachment; filename="{r.filename}"')
        self.security_headers()
        self.end_headers()
        self.wfile.write(r.body)

    def security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        if self.server.tls:
            self.send_header("Strict-Transport-Security", "max-age=31536000")

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            raise ApiError(413, "Request too large")
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise ApiError(400, "Invalid JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "Expected a JSON object")
        return data

    def cookie_token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "pos_session":
                return v
        return None

    def current_user(self, conn):
        token = self.cookie_token()
        if not token:
            return None
        row = conn.execute(
            "SELECT u.id, u.name, u.role FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token=? AND s.expires>? AND u.active=1",
            (token, time.time()),
        ).fetchone()
        return dict(row) if row else None

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def dispatch(self, method):
        url = urlparse(self.path)
        if url.path == "/t" and method == "GET":
            # Tag link scanned by a phone's camera app: open the stocktake screen.
            c = parse_qs(url.query).get("c", [""])[0]
            return self.redirect("/scan.html?mode=count&code=" + quote(c, safe=""))
        if not url.path.startswith("/api/"):
            if method != "GET":
                return self.send_json(405, {"error": "Method not allowed"})
            return self.serve_static(url.path)
        if method != "GET" and self.headers.get("X-Requested-With") != "pos":
            return self.send_json(403, {"error": "Missing request header"})
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        conn = connect()
        try:
            for m, pattern, func, role in self.routes:
                if m != method:
                    continue
                match = pattern.match(url.path)
                if not match:
                    continue
                user = self.current_user(conn)
                if role and not user:
                    raise ApiError(401, "Please log in")
                if role == "owner" and user["role"] != "owner":
                    raise ApiError(403, "Owner access required")
                data = self.read_json() if method in ("POST", "PUT") else {}
                result = func(self, conn, user, q, data, *match.groups())
                conn.commit()
                if isinstance(result, RawResponse):
                    return self.send_raw(result)
                if isinstance(result, tuple):
                    return self.send_json(200, result[0], result[1])
                return self.send_json(200, result)
            raise ApiError(404, "Not found")
        except ApiError as e:
            conn.rollback()
            self.send_json(e.status, {"error": e.message})
        except sqlite3.IntegrityError as e:
            conn.rollback()
            msg = "That SKU is already used" if "sku" in str(e) else "That conflicts with existing data"
            self.send_json(409, {"error": msg})
        except Exception as e:  # pragma: no cover
            conn.rollback()
            sys.stderr.write(f"Error: {e!r}\n")
            self.send_json(500, {"error": "Server error"})
        finally:
            conn.close()

    def serve_static(self, path):
        if path in ("", "/"):
            path = "/register.html"
        full = os.path.realpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep) or not os.path.isfile(full):
            body = b"Not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    tls = True

    def handle_error(self, request, client_address):
        # Phones that reject a self-signed certificate, or drop off Wi-Fi, are normal.
        if isinstance(sys.exc_info()[1], (ssl.SSLError, ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def route(method, path, role="any"):
    """role: None = public, 'any' = logged in, 'owner' = owner only."""
    def deco(func):
        Handler.routes.append((method, re.compile("^" + path + "$"), func, role))
        return func
    return deco


# ---------------------------------------------------------------- auth

@route("GET", "/api/users/public", role=None)
def users_public(h, conn, user, q, data):
    rows = conn.execute("SELECT id, name, role FROM users WHERE active=1 ORDER BY name")
    return {"users": [dict(r) for r in rows],
            "shop_name": get_settings(conn)["shop_name"]}


@route("POST", "/api/login", role=None)
def login(h, conn, user, q, data):
    ip = h.client_address[0]
    with login_lock:
        fails, until = login_fails.get(ip, (0, 0))
        if until > time.time():
            raise ApiError(429, f"Too many attempts. Try again in {int(until - time.time()) + 1}s")
    uid = req_int(data, "user_id", 1)
    pin = req_str(data, "pin", 12)
    u = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
    if not u or not hmac.compare_digest(u["pin_hash"], hash_pin(pin, u["salt"])):
        with login_lock:
            fails += 1
            login_fails[ip] = (0, time.time() + LOCKOUT_SECONDS) if fails >= MAX_LOGIN_FAILS else (fails, 0)
        raise ApiError(401, "Wrong PIN")
    with login_lock:
        login_fails.pop(ip, None)
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
    conn.execute("INSERT INTO sessions VALUES (?,?,?)",
                 (token, u["id"], time.time() + SESSION_HOURS * 3600))
    audit(conn, u["id"], "login")
    secure = "; Secure" if h.server.tls else ""
    cookie = f"pos_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS * 3600}{secure}"
    return {"id": u["id"], "name": u["name"], "role": u["role"]}, {"Set-Cookie": cookie}


@route("POST", "/api/logout")
def logout(h, conn, user, q, data):
    conn.execute("DELETE FROM sessions WHERE token=?", (h.cookie_token(),))
    return {"ok": True}, {"Set-Cookie": "pos_session=; Path=/; Max-Age=0"}


@route("GET", "/api/me")
def me(h, conn, user, q, data):
    return {"user": user, "settings": get_settings(conn)}


# ---------------------------------------------------------------- products

PRODUCT_FIELDS = "id, sku, name, vendor_code, category, price_cents, cost_cents, stock, reorder_level, gst_free, active, updated_at"


def product_out(row, hide_cost):
    p = dict(row)
    if hide_cost:
        p.pop("cost_cents", None)
    return p


@route("GET", "/api/products")
def list_products(h, conn, user, q, data):
    sql = f"SELECT {PRODUCT_FIELDS} FROM products"
    args = []
    where = [] if q.get("all") == "1" else ["active=1"]
    if q.get("q"):
        where.append("(name LIKE ? OR sku LIKE ? OR vendor_code LIKE ? OR category LIKE ?)")
        args += ["%" + q["q"] + "%"] * 4
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name LIMIT 500"
    hide = user["role"] != "owner"
    return {"products": [product_out(r, hide) for r in conn.execute(sql, args)]}


@route("GET", "/api/products/lookup")
def lookup_product(h, conn, user, q, data):
    sku, tag_price = parse_scan(q.get("code", ""))
    if not sku:
        raise ApiError(400, "Nothing scanned")
    row = conn.execute(f"SELECT {PRODUCT_FIELDS} FROM products WHERE sku=?", (sku,)).fetchone()
    if not row:
        raise ApiError(404, f"No product with SKU {sku}")
    p = product_out(row, user["role"] != "owner")
    return {"product": p,
            "tag_price_cents": tag_price,
            "tag_outdated": tag_price is not None and tag_price != row["price_cents"]}


def product_fields(data, partial=False):
    out = {}
    if not partial or "name" in data:
        out["name"] = req_str(data, "name", 80)
    if not partial or "vendor_code" in data:
        v = req_str(data, "vendor_code", 20, required=False)
        if "|" in v:
            raise ApiError(400, "Vendor code can't contain |")
        out["vendor_code"] = v
    if not partial or "category" in data:
        out["category"] = req_str(data, "category", 40, required=False)
    if not partial or "price_cents" in data:
        out["price_cents"] = req_int(data, "price_cents", 0, 10_000_00)
    if not partial or "cost_cents" in data:
        out["cost_cents"] = req_int(data, "cost_cents", 0, 10_000_00, default=0)
    if not partial or "reorder_level" in data:
        out["reorder_level"] = req_int(data, "reorder_level", 0, 100_000, default=0)
    if not partial or "gst_free" in data:
        out["gst_free"] = 1 if data.get("gst_free") else 0
    if partial and "active" in data:
        out["active"] = 1 if data.get("active") else 0
    return out


@route("POST", "/api/products", role="owner")
def create_product(h, conn, user, q, data):
    f = product_fields(data)
    sku = req_str(data, "sku", 16, required=False).upper()
    if sku and not SKU_RE.match(sku):
        raise ApiError(400, "SKU can only use letters, numbers and -")
    stock = req_int(data, "stock", 0, 100_000, default=0)
    cur = conn.execute(
        "INSERT INTO products (sku, name, vendor_code, category, price_cents, cost_cents, "
        "stock, reorder_level, gst_free, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sku or "TMP-" + secrets.token_hex(4), f["name"], f["vendor_code"], f["category"],
         f["price_cents"], f["cost_cents"], stock, f["reorder_level"], f["gst_free"], ts(conn)),
    )
    pid = cur.lastrowid
    if not sku:
        sku = f"P{pid:04d}"
        conn.execute("UPDATE products SET sku=? WHERE id=?", (sku, pid))
    if stock:
        conn.execute(
            "INSERT INTO stock_moves (created_at, product_id, qty_change, reason, note, user_id) "
            "VALUES (?,?,?,?,?,?)", (ts(conn), pid, stock, "initial", "", user["id"]))
    audit(conn, user["id"], "product_create", f"{sku} {f['name']}")
    row = conn.execute(f"SELECT {PRODUCT_FIELDS} FROM products WHERE id=?", (pid,)).fetchone()
    return {"product": dict(row)}


@route("PUT", r"/api/products/(\d+)", role="owner")
def update_product(h, conn, user, q, data, pid):
    old = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not old:
        raise ApiError(404, "Product not found")
    f = product_fields(data, partial=True)
    if not f:
        raise ApiError(400, "Nothing to update")
    sets = ", ".join(f"{k}=?" for k in f) + ", updated_at=?"
    conn.execute(f"UPDATE products SET {sets} WHERE id=?", (*f.values(), ts(conn), pid))
    if "price_cents" in f and f["price_cents"] != old["price_cents"]:
        audit(conn, user["id"], "price_change",
              f"{old['sku']} {old['price_cents']} -> {f['price_cents']}")
    row = conn.execute(f"SELECT {PRODUCT_FIELDS} FROM products WHERE id=?", (pid,)).fetchone()
    return {"product": dict(row)}


# ---------------------------------------------------------------- stock

@route("POST", "/api/stock/receive")
def stock_receive(h, conn, user, q, data):
    pid = req_int(data, "product_id", 1)
    qty = req_int(data, "qty", 1, 100_000)
    note = req_str(data, "note", 120, required=False)
    if not conn.execute("SELECT 1 FROM products WHERE id=?", (pid,)).fetchone():
        raise ApiError(404, "Product not found")
    conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (qty, pid))
    conn.execute(
        "INSERT INTO stock_moves (created_at, product_id, qty_change, reason, note, user_id) "
        "VALUES (?,?,?,?,?,?)", (ts(conn), pid, qty, "receive", note, user["id"]))
    return {"stock": conn.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()[0]}


@route("POST", "/api/stock/count", role="owner")
def stock_count(h, conn, user, q, data):
    """Set stock to a counted figure (stocktake) or adjust with a reason."""
    pid = req_int(data, "product_id", 1)
    counted = req_int(data, "counted", 0, 100_000)
    reason = req_str(data, "reason", 20, required=False) or "stocktake"
    if reason not in ("stocktake", "damaged", "lost", "store_use", "correction"):
        raise ApiError(400, "Unknown reason")
    note = req_str(data, "note", 120, required=False)
    row = conn.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
    if not row:
        raise ApiError(404, "Product not found")
    diff = counted - row["stock"]
    if diff:
        conn.execute("UPDATE products SET stock=? WHERE id=?", (counted, pid))
        conn.execute(
            "INSERT INTO stock_moves (created_at, product_id, qty_change, reason, note, user_id) "
            "VALUES (?,?,?,?,?,?)", (ts(conn), pid, diff, reason, note, user["id"]))
    return {"stock": counted, "change": diff}


@route("GET", "/api/stock/moves")
def stock_moves(h, conn, user, q, data):
    pid = req_int(q, "product_id", 1)
    rows = conn.execute(
        "SELECT m.created_at, m.qty_change, m.reason, m.note, m.sale_id, u.name AS user "
        "FROM stock_moves m LEFT JOIN users u ON u.id = m.user_id "
        "WHERE m.product_id=? ORDER BY m.id DESC LIMIT 100", (pid,))
    return {"moves": [dict(r) for r in rows]}


# ---------------------------------------------------------------- sales

@route("POST", "/api/sales/quote")
def quote_sale(h, conn, user, q, data):
    lines, totals = build_sale(conn, data.get("items"), data.get("payment") or {"method": "card"})
    totals["cash_total_cents"] = round_cash(totals["subtotal_cents"])
    return {"lines": lines, **totals}


@route("POST", "/api/sales")
def create_sale(h, conn, user, q, data):
    lines, t = build_sale(conn, data.get("items"), data.get("payment"))
    now = ts(conn)
    cur = conn.execute(
        "INSERT INTO sales (created_at, user_id, subtotal_cents, gst_cents, rounding_cents, total_cents, "
        "payment_method, cash_cents, card_cents, tendered_cents, change_cents, card_ref) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (now, user["id"], t["subtotal_cents"], t["gst_cents"], t["rounding_cents"], t["total_cents"],
         t["payment_method"], t["cash_cents"], t["card_cents"], t["tendered_cents"],
         t["change_cents"], t["card_ref"]))
    sid = cur.lastrowid
    for l in lines:
        conn.execute(
            "INSERT INTO sale_items (sale_id, product_id, sku, name, qty, unit_price_cents, "
            "line_total_cents, gst_cents, cost_cents) VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, l["product_id"], l["sku"], l["name"], l["qty"], l["unit_price_cents"],
             l["line_total_cents"], l["gst_cents"], l["cost_cents"]))
        if l["product_id"]:
            conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (l["qty"], l["product_id"]))
            conn.execute(
                "INSERT INTO stock_moves (created_at, product_id, qty_change, reason, user_id, sale_id) "
                "VALUES (?,?,?,?,?,?)", (now, l["product_id"], -l["qty"], "sale", user["id"], sid))
    return {"sale": sale_detail(conn, sid)}


@route("GET", r"/api/sales/(\d+)")
def get_sale(h, conn, user, q, data, sid):
    return {"sale": sale_detail(conn, int(sid)), "settings": get_settings(conn)}


@route("GET", "/api/sales")
def list_sales(h, conn, user, q, data):
    frm, to = day_range(q)
    rows = conn.execute(
        "SELECT s.id, s.created_at, s.kind, s.refund_of, s.refunded_by, s.total_cents, "
        "s.payment_method, u.name AS cashier, "
        "(SELECT COALESCE(SUM(qty),0) FROM sale_items WHERE sale_id=s.id) AS item_count "
        "FROM sales s JOIN users u ON u.id = s.user_id "
        "WHERE s.created_at >= ? AND s.created_at < ? ORDER BY s.id DESC LIMIT 1000", (frm, to))
    return {"sales": [dict(r) for r in rows]}


@route("POST", r"/api/sales/(\d+)/refund", role="owner")
def refund_sale(h, conn, user, q, data, sid):
    s = conn.execute("SELECT * FROM sales WHERE id=?", (sid,)).fetchone()
    if not s:
        raise ApiError(404, "Sale not found")
    if s["kind"] != "sale" or s["refunded_by"]:
        raise ApiError(400, "This sale can't be refunded (already refunded or is a refund)")
    restock = bool(data.get("restock", True))
    now = ts(conn)
    neg = {k: -s[k] for k in ("subtotal_cents", "gst_cents", "rounding_cents", "total_cents",
                              "cash_cents", "card_cents")}
    cur = conn.execute(
        "INSERT INTO sales (created_at, user_id, kind, refund_of, subtotal_cents, gst_cents, "
        "rounding_cents, total_cents, payment_method, cash_cents, card_cents, card_ref) "
        "VALUES (?,?,'refund',?,?,?,?,?,?,?,?,?)",
        (now, user["id"], s["id"], neg["subtotal_cents"], neg["gst_cents"], neg["rounding_cents"],
         neg["total_cents"], s["payment_method"], neg["cash_cents"], neg["card_cents"],
         req_str(data, "card_ref", 40, required=False)))
    rid = cur.lastrowid
    for it in conn.execute("SELECT * FROM sale_items WHERE sale_id=?", (sid,)).fetchall():
        conn.execute(
            "INSERT INTO sale_items (sale_id, product_id, sku, name, qty, unit_price_cents, "
            "line_total_cents, gst_cents, cost_cents) VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, it["product_id"], it["sku"], it["name"], -it["qty"], it["unit_price_cents"],
             -it["line_total_cents"], -it["gst_cents"], it["cost_cents"]))
        if restock and it["product_id"]:
            conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (it["qty"], it["product_id"]))
            conn.execute(
                "INSERT INTO stock_moves (created_at, product_id, qty_change, reason, user_id, sale_id) "
                "VALUES (?,?,?,?,?,?)", (now, it["product_id"], it["qty"], "refund", user["id"], rid))
    conn.execute("UPDATE sales SET refunded_by=? WHERE id=?", (rid, sid))
    audit(conn, user["id"], "refund", f"sale {sid} -> refund {rid}")
    return {"sale": sale_detail(conn, rid)}


# ---------------------------------------------------------------- reports

@route("GET", "/api/reports/summary")
def report_summary(h, conn, user, q, data):
    frm, to = day_range(q)
    if user["role"] != "owner" and (q["from"] != q["to"] or q["from"] != now_local(conn).date().isoformat()):
        raise ApiError(403, "Cashiers can only view today's summary")
    rng = (frm, to)
    t = dict(conn.execute(
        "SELECT COUNT(CASE WHEN kind='sale' THEN 1 END) AS sale_count, "
        "COALESCE(SUM(CASE WHEN kind='sale' THEN total_cents END),0) AS gross_cents, "
        "COALESCE(-SUM(CASE WHEN kind='refund' THEN total_cents END),0) AS refunds_cents, "
        "COALESCE(SUM(total_cents),0) AS net_cents, "
        "COALESCE(SUM(gst_cents),0) AS gst_cents, "
        "COALESCE(SUM(rounding_cents),0) AS rounding_cents, "
        "COALESCE(SUM(cash_cents),0) AS cash_cents, "
        "COALESCE(SUM(card_cents),0) AS card_cents "
        "FROM sales WHERE created_at >= ? AND created_at < ?", rng).fetchone())
    t["avg_sale_cents"] = t["gross_cents"] // t["sale_count"] if t["sale_count"] else 0
    cost = conn.execute(
        "SELECT COALESCE(SUM(i.cost_cents * i.qty),0) FROM sale_items i JOIN sales s ON s.id=i.sale_id "
        "WHERE s.created_at >= ? AND s.created_at < ?", rng).fetchone()[0]
    if user["role"] == "owner":
        t["cost_cents"] = cost
        t["gross_profit_cents"] = (t["net_cents"] - t["gst_cents"] - t["rounding_cents"]) - cost
    top = conn.execute(
        "SELECT i.name, i.sku, SUM(i.qty) AS qty, SUM(i.line_total_cents) AS sales_cents "
        "FROM sale_items i JOIN sales s ON s.id=i.sale_id "
        "WHERE s.created_at >= ? AND s.created_at < ? GROUP BY i.product_id, i.name "
        "HAVING SUM(i.qty) > 0 ORDER BY sales_cents DESC LIMIT 10", rng)
    hourly = conn.execute(
        "SELECT CAST(substr(created_at, 12, 2) AS INTEGER) AS hour, SUM(total_cents) AS cents, "
        "COUNT(CASE WHEN kind='sale' THEN 1 END) AS count "
        "FROM sales WHERE created_at >= ? AND created_at < ? GROUP BY hour ORDER BY hour", rng)
    daily = conn.execute(
        "SELECT substr(created_at, 1, 10) AS day, SUM(total_cents) AS cents, "
        "COUNT(CASE WHEN kind='sale' THEN 1 END) AS count "
        "FROM sales WHERE created_at >= ? AND created_at < ? GROUP BY day ORDER BY day", rng)
    cashiers = conn.execute(
        "SELECT u.name, COUNT(CASE WHEN s.kind='sale' THEN 1 END) AS count, SUM(s.total_cents) AS cents "
        "FROM sales s JOIN users u ON u.id=s.user_id "
        "WHERE s.created_at >= ? AND s.created_at < ? GROUP BY u.id ORDER BY cents DESC", rng)
    return {"totals": t, "top": [dict(r) for r in top], "hourly": [dict(r) for r in hourly],
            "daily": [dict(r) for r in daily], "cashiers": [dict(r) for r in cashiers]}


@route("GET", "/api/reports/stock")
def report_stock(h, conn, user, q, data):
    hide = user["role"] != "owner"
    low = conn.execute(
        f"SELECT {PRODUCT_FIELDS} FROM products WHERE active=1 AND stock <= reorder_level "
        "ORDER BY stock - reorder_level, name")
    out = {"low": [product_out(r, hide) for r in low]}
    v = conn.execute(
        "SELECT COUNT(*) AS products, COALESCE(SUM(MAX(stock,0)),0) AS units, "
        "COALESCE(SUM(MAX(stock,0) * price_cents),0) AS retail_cents, "
        "COALESCE(SUM(MAX(stock,0) * cost_cents),0) AS cost_cents, "
        "COUNT(CASE WHEN stock < 0 THEN 1 END) AS negative "
        "FROM products WHERE active=1").fetchone()
    out["value"] = dict(v)
    if hide:
        out["value"].pop("cost_cents")
    return out


@route("GET", "/api/audit", role="owner")
def audit_list(h, conn, user, q, data):
    frm, to = day_range(q)
    rows = conn.execute(
        "SELECT a.created_at, a.action, a.detail, u.name AS user FROM audit_log a "
        "LEFT JOIN users u ON u.id=a.user_id WHERE a.created_at >= ? AND a.created_at < ? "
        "AND a.action != 'login' ORDER BY a.id DESC LIMIT 500", (frm, to))
    return {"entries": [dict(r) for r in rows]}


# ---------------------------------------------------------------- cash up

def expected_cash(conn, day):
    nxt = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    return conn.execute(
        "SELECT COALESCE(SUM(cash_cents),0) FROM sales WHERE created_at >= ? AND created_at < ?",
        (day + " 00:00:00", nxt + " 00:00:00")).fetchone()[0]


@route("GET", "/api/cashup")
def get_cashup(h, conn, user, q, data):
    day = q.get("day") or now_local(conn).date().isoformat()
    if not DATE_RE.match(day):
        raise ApiError(400, "Bad date")
    saved = [dict(r) for r in conn.execute(
        "SELECT c.*, u.name AS user FROM cash_ups c JOIN users u ON u.id=c.user_id "
        "WHERE day=? ORDER BY c.id DESC", (day,))]
    return {"day": day, "cash_sales_cents": expected_cash(conn, day), "saved": saved}


@route("POST", "/api/cashup")
def save_cashup(h, conn, user, q, data):
    day = now_local(conn).date().isoformat()
    float_c = req_int(data, "float_cents", 0, 100_000_00)
    counted = req_int(data, "counted_cents", 0, 100_000_00)
    expected = float_c + expected_cash(conn, day)
    conn.execute(
        "INSERT INTO cash_ups (day, created_at, user_id, float_cents, expected_cents, counted_cents, "
        "diff_cents, note) VALUES (?,?,?,?,?,?,?,?)",
        (day, ts(conn), user["id"], float_c, expected, counted, counted - expected,
         req_str(data, "note", 200, required=False)))
    return {"expected_cents": expected, "diff_cents": counted - expected}


# ---------------------------------------------------------------- settings & users

@route("GET", "/api/settings", role="owner")
def read_settings(h, conn, user, q, data):
    users = conn.execute("SELECT id, name, role, active FROM users ORDER BY name")
    return {"settings": get_settings(conn), "users": [dict(u) for u in users]}


@route("PUT", "/api/settings", role="owner")
def write_settings(h, conn, user, q, data):
    for key in DEFAULT_SETTINGS:
        if key in data:
            val = req_str(data, key, 200, required=False)
            if key == "tag_base_url":
                val = val.rstrip("/")
                if val and not re.match(r"^https?://[^/\s?#]+$", val):
                    raise ApiError(400, "Tag web address should look like https://192.168.1.20")
            if key == "timezone" and ZoneInfo:
                try:
                    ZoneInfo(val)
                except Exception:
                    raise ApiError(400, "Unknown timezone")
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, val))
    audit(conn, user["id"], "settings_change")
    return {"settings": get_settings(conn)}


def valid_pin(data):
    pin = req_str(data, "pin", 12)
    if not pin.isdigit() or len(pin) < 4:
        raise ApiError(400, "PIN must be 4-12 digits")
    return pin


@route("POST", "/api/users", role="owner")
def create_user(h, conn, user, q, data):
    name = req_str(data, "name", 40)
    role = data.get("role")
    if role not in ("owner", "cashier"):
        raise ApiError(400, "Role must be owner or cashier")
    salt = secrets.token_hex(16)
    conn.execute("INSERT INTO users (name, role, pin_hash, salt) VALUES (?,?,?,?)",
                 (name, role, hash_pin(valid_pin(data), salt), salt))
    audit(conn, user["id"], "user_create", f"{name} ({role})")
    return {"ok": True}


@route("PUT", r"/api/users/(\d+)", role="owner")
def update_user(h, conn, user, q, data, uid):
    uid = int(uid)
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        raise ApiError(404, "User not found")
    if "pin" in data:
        salt = secrets.token_hex(16)
        conn.execute("UPDATE users SET pin_hash=?, salt=? WHERE id=?",
                     (hash_pin(valid_pin(data), salt), salt, uid))
        conn.execute("DELETE FROM sessions WHERE user_id=? AND token != ?", (uid, h.cookie_token()))
    if "role" in data or "active" in data:
        role = data.get("role", u["role"])
        active = 1 if data.get("active", u["active"]) else 0
        if role not in ("owner", "cashier"):
            raise ApiError(400, "Role must be owner or cashier")
        owners = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='owner' AND active=1 AND id != ?", (uid,)).fetchone()[0]
        if (role != "owner" or not active) and owners == 0:
            raise ApiError(400, "There must be at least one active owner")
        conn.execute("UPDATE users SET role=?, active=? WHERE id=?", (role, active, uid))
        if not active:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    audit(conn, user["id"], "user_update", u["name"])
    return {"ok": True}


@route("GET", "/api/backup", role="owner")
def backup(h, conn, user, q, data):
    path = os.path.join(DATA_DIR, f"backup-{secrets.token_hex(4)}.db")
    try:
        dest = sqlite3.connect(path)
        conn.backup(dest)
        dest.close()
        with open(path, "rb") as f:
            body = f.read()
    finally:
        if os.path.exists(path):
            os.remove(path)
    name = "pos-backup-" + now_local(conn).strftime("%Y%m%d-%H%M") + ".db"
    return RawResponse(body, "application/octet-stream", name)


# ---------------------------------------------------------------- startup

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ensure_self_signed(cert, key):
    """Create a self-signed certificate for testing on the shop network."""
    if os.path.exists(cert) and os.path.exists(key):
        return
    ip = lan_ip()
    san = f"DNS:localhost,DNS:{socket.gethostname()},IP:127.0.0.1"
    try:
        ipaddress.ip_address(ip)
        san += f",IP:{ip}"
    except ValueError:
        pass
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "825",
         "-keyout", key, "-out", cert, "-subj", "/CN=pos.local", "-addext", f"subjectAltName={san}"],
        check=True, capture_output=True)
    os.chmod(key, 0o600)
    print(f"Created self-signed certificate ({san})")


def main():
    ap = argparse.ArgumentParser(description="Lightweight POS server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=443)
    ap.add_argument("--cert", help="TLS certificate (PEM). Default: self-signed in data/")
    ap.add_argument("--key", help="TLS private key (PEM)")
    ap.add_argument("--http", action="store_true",
                    help="Plain HTTP (only behind a TLS proxy such as Caddy, bound to 127.0.0.1)")
    args = ap.parse_args()

    init_db()
    httpd = Server((args.host, args.port), Handler)
    httpd.tls = not args.http
    if httpd.tls:
        cert = args.cert or os.path.join(DATA_DIR, "cert.pem")
        key = args.key or os.path.join(DATA_DIR, "key.pem")
        if not args.cert:
            ensure_self_signed(cert, key)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        # Handshake happens in the request thread so a slow client can't block others.
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True, do_handshake_on_connect=False)
    scheme = "https" if httpd.tls else "http"
    port = "" if args.port in (80, 443) else f":{args.port}"
    print(f"POS running at {scheme}://{lan_ip()}{port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
