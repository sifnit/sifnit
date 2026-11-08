#!/usr/bin/env python3
"""Run Product Camera from this PC over HTTPS, and finish every photo the phone sends.

    python serve.py                 # port 8443, photos go to ./photos
    python serve.py --port 9000 --out D:\\Listings

For each photo taken in the app, the PC saves the original to photos/originals and a finished
image to photos/finished: item cut out, light feather, centred on white 1000x1000, named
<object>_<date>.jpg (object = the Set name in the app).

The phone and this PC must be on the same Wi-Fi. Chrome warns the first time because the
certificate is self-signed: tap Advanced, then Proceed.
"""
import argparse
import datetime
import http.server
import ipaddress
import json
import queue
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CERT_DIR = HERE / ".cert"
CERT, KEY = CERT_DIR / "cert.pem", CERT_DIR / "key.pem"
IP_FILE = CERT_DIR / "ip.txt"

# Only these files are served. Nothing else in the folder (certificate key, photos) is reachable.
APP_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
    "/sw.js": ("sw.js", "text/javascript"),
}
MAX_UPLOAD = 60 * 1024 * 1024


# ---------------- certificate ----------------
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; this just picks the outward interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def make_cert_cryptography(ip):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Product Camera")])
    now = datetime.datetime.now(datetime.timezone.utc)
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address(ip)),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=825))
            .add_extension(san, critical=False).sign(key, hashes.SHA256()))
    KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def make_cert_openssl(ip):
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", str(KEY), "-out", str(CERT), "-days", "825", "-subj", "/CN=Product Camera",
        "-addext", f"subjectAltName=DNS:localhost,IP:{ip},IP:127.0.0.1",
    ], check=True, capture_output=True)


def ensure_cert(ip):
    # Reuse the certificate unless this PC's network address changed.
    if CERT.exists() and KEY.exists() and IP_FILE.exists() and IP_FILE.read_text().strip() == ip:
        return
    CERT_DIR.mkdir(exist_ok=True)
    try:
        make_cert_cryptography(ip)
    except ImportError:
        if not shutil.which("openssl"):
            sys.exit("Need the 'cryptography' Python package to make a certificate.\n"
                     "Install it with:  pip install -r requirements.txt")
        make_cert_openssl(ip)
    IP_FILE.write_text(ip)
    print("Made a new self-signed certificate.")


# ---------------- background processing ----------------
class Worker:
    """Finishes photos one at a time so the phone never waits on the cutout."""

    def __init__(self, out_dir):
        self.originals = out_dir / "originals"
        self.finished = out_dir / "finished"
        self.originals.mkdir(parents=True, exist_ok=True)
        self.finished.mkdir(parents=True, exist_ok=True)
        self.q = queue.Queue()
        self.done = 0
        self.failed = 0
        self.last = None
        self.busy = False
        self.ready = False
        self.error = None
        threading.Thread(target=self.run, daemon=True).start()

    def status(self):
        return {"ok": True, "queued": self.q.qsize() + (1 if self.busy else 0), "done": self.done,
                "failed": self.failed, "last": self.last, "ready": self.ready, "error": self.error}

    def run(self):
        try:
            import process
            ram = process.total_ram_gb()
            if process.MODEL != "birefnet-general":
                print(f"This PC has {ram:.0f} GB of RAM, so it's using the lighter cutout model. "
                      "Edges may be a little less precise; 16 GB of RAM gets the best one.", flush=True)
            process.session()  # load (and on first run download) the model up front
            self.ready = True
            print("Cutout model loaded. Ready for photos.", flush=True)
        except Exception as e:
            self.error = f"Cutout isn't working: {e}. Run: pip install -r requirements.txt"
            print(self.error, flush=True)
            return
        while True:
            src, name, taken = self.q.get()
            self.busy = True
            try:
                dst = process.process_file(src, self.finished, name, taken)
                self.done += 1
                self.last = dst.name
                print(f"  finished  {dst.name}", flush=True)
            except Exception as e:
                self.failed += 1
                print(f"  FAILED    {src.name}: {e}", flush=True)
            finally:
                self.busy = False

    def add(self, data, name, taken, ext):
        stamp = taken.strftime("%Y%m%d-%H%M%S-%f")
        src = self.originals / f"{process_clean(name)}_{stamp}{ext}"
        src.write_bytes(data)
        self.q.put((src, name, taken))
        return src


def process_clean(name):
    import re
    return re.sub(r"[^\w-]+", "-", (name or "").strip().lower()).strip("-_") or "product"


# ---------------- web server ----------------
def make_handler(worker):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send_body(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def json(self, code, obj):
            self.send_body(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/status":
                return self.json(200, worker.status())
            if path in APP_FILES:
                fname, ctype = APP_FILES[path]
                return self.send_body(200, (HERE / fname).read_bytes(), ctype)
            self.send_body(404, b"Not found", "text/plain")

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/api/upload":
                return self.send_body(404, b"Not found", "text/plain")
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_UPLOAD:
                return self.json(413, {"ok": False, "error": "photo too large"})
            data = self.rfile.read(length)
            ctype = (self.headers.get("Content-Type") or "").lower()
            ext = ".png" if "png" in ctype else ".webp" if "webp" in ctype else ".jpg"
            name = self.headers.get("X-Object-Name") or "product"
            try:
                taken = datetime.datetime.fromtimestamp(int(self.headers.get("X-Taken")) / 1000)
            except (TypeError, ValueError):
                taken = datetime.datetime.now()
            worker.add(data, name, taken, ext)
            self.json(200, {"ok": True, **worker.status()})

    return Handler


def main():
    p = argparse.ArgumentParser(description="Run Product Camera from this PC.")
    p.add_argument("--port", type=int, default=8443)
    p.add_argument("--out", default=str(HERE / "photos"), help="where photos are saved (default: ./photos)")
    args = p.parse_args()

    ip = lan_ip()
    ensure_cert(ip)
    out = Path(args.out).expanduser().resolve()
    sys.path.insert(0, str(HERE))
    worker = Worker(out)

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(worker))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print(f"\nProduct Camera is running.\n\n  On your phone, open:  https://{ip}:{args.port}\n")
    print("  Chrome will warn that the connection isn't private (the certificate is self-signed).")
    print("  Tap Advanced, then Proceed. Phone and PC must be on the same Wi-Fi.")
    print(f"\n  Finished photos:  {worker.finished}")
    print(f"  Originals:        {worker.originals}")
    print("\nPress Ctrl+C to stop.\n", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
