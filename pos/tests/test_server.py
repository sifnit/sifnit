"""End-to-end API tests. Run from the pos/ folder:  python3 -m unittest discover tests"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer  # noqa: F401

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["POS_DATA_DIR"] = tempfile.mkdtemp(prefix="pos-test-")
os.environ["POS_QUIET"] = "1"
import server  # noqa: E402


class Client:
    def __init__(self, port):
        self.port = port
        self.cookie = None

    def call(self, method, path, body=None, raw=False):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        headers = {"X-Requested-With": "pos"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body)
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse()
        data = r.read()
        sc = r.getheader("Set-Cookie")
        if sc:
            self.cookie = sc.split(";")[0]
        c.close()
        return r.status, (data if raw else json.loads(data or b"{}"))

    def ok(self, method, path, body=None):
        status, data = self.call(method, path, body)
        assert status == 200, (status, data)
        return data


class PureFunctions(unittest.TestCase):
    def test_cash_rounding(self):
        cases = {0: 0, 1: 0, 2: 0, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5, 8: 10, 9: 10, 1234: 1235, 1237: 1235, 1238: 1240}
        for cents, want in cases.items():
            self.assertEqual(server.round_cash(cents), want, cents)
        self.assertEqual(server.round_cash(-1237), -1235)

    def test_gst(self):
        self.assertEqual(server.gst_of(1100), 100)
        self.assertEqual(server.gst_of(1000), 91)
        self.assertEqual(server.gst_of(-1100), -100)

    def test_parse_scan(self):
        self.assertEqual(server.parse_scan("p0001|ACME-1|12.50"), ("P0001", 1250))
        self.assertEqual(server.parse_scan(" P0002 "), ("P0002", None))
        self.assertEqual(server.parse_scan("https://10.0.0.5:8443/t?c=P0003|V%20X|5.00"), ("P0003", 500))
        self.assertEqual(server.parse_scan("https://10.0.0.5/t?c=P0004%7CV%7C1.00"), ("P0004", 100))


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.init_db()
        cls.httpd = server.Server(("127.0.0.1", 0), server.Handler)
        cls.httpd.tls = False
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.port = cls.httpd.server_address[1]
        cls.owner = Client(cls.port)
        users = cls.owner.ok("GET", "/api/users/public")["users"]
        cls.owner_id = users[0]["id"]
        cls.owner.ok("POST", "/api/login", {"user_id": cls.owner_id, "pin": "1234"})

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def product(self, **kw):
        body = {"name": "Widget", "vendor_code": "ACME-1", "price_cents": 1234, "cost_cents": 500, "stock": 10}
        body.update(kw)
        return self.owner.ok("POST", "/api/products", body)["product"]

    def test_requires_login_and_header(self):
        anon = Client(self.port)
        self.assertEqual(anon.call("GET", "/api/products")[0], 401)
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("POST", "/api/logout", headers={"Cookie": self.owner.cookie})
        self.assertEqual(c.getresponse().status, 403)

    def test_wrong_pin(self):
        status, data = Client(self.port).call("POST", "/api/login", {"user_id": self.owner_id, "pin": "0000"})
        self.assertEqual(status, 401)

    def test_product_sku_and_lookup(self):
        p = self.product()
        self.assertRegex(p["sku"], r"^P\d{4}$")
        payload = f"{p['sku']}|ACME-1|12.34"
        r = self.owner.ok("GET", "/api/products/lookup?code=" + payload.replace("|", "%7C"))
        self.assertEqual(r["product"]["id"], p["id"])
        self.assertFalse(r["tag_outdated"])
        r = self.owner.ok("GET", f"/api/products/lookup?code={p['sku']}%7CX%7C9.99")
        self.assertTrue(r["tag_outdated"])
        status, _ = self.owner.call("POST", "/api/products", {"name": "Dup", "sku": p["sku"], "price_cents": 1})
        self.assertEqual(status, 409)

    def test_cash_sale_rounding_stock_and_refund(self):
        p = self.product(price_cents=1237, stock=5)
        sale = self.owner.ok("POST", "/api/sales", {
            "items": [{"product_id": p["id"], "qty": 2, "price_cents": 1}],  # client price ignored
            "payment": {"method": "cash", "tendered_cents": 3000}})["sale"]
        self.assertEqual(sale["subtotal_cents"], 2474)
        self.assertEqual(sale["total_cents"], 2475)
        self.assertEqual(sale["rounding_cents"], 1)
        self.assertEqual(sale["change_cents"], 525)
        self.assertEqual(sale["gst_cents"], 225)
        stock = self.owner.ok("GET", f"/api/products/lookup?code={p['sku']}")["product"]["stock"]
        self.assertEqual(stock, 3)

        refund = self.owner.ok("POST", f"/api/sales/{sale['id']}/refund", {})["sale"]
        self.assertEqual(refund["total_cents"], -2475)
        stock = self.owner.ok("GET", f"/api/products/lookup?code={p['sku']}")["product"]["stock"]
        self.assertEqual(stock, 5)
        status, _ = self.owner.call("POST", f"/api/sales/{sale['id']}/refund", {})
        self.assertEqual(status, 400)

    def test_card_split_and_validation(self):
        p = self.product(price_cents=1000)
        card = self.owner.ok("POST", "/api/sales", {
            "items": [{"product_id": p["id"], "qty": 1}], "payment": {"method": "card"}})["sale"]
        self.assertEqual((card["card_cents"], card["cash_cents"], card["rounding_cents"]), (1000, 0, 0))
        split = self.owner.ok("POST", "/api/sales", {
            "items": [{"product_id": p["id"], "qty": 1}, {"name": "Bag", "price_cents": 7, "qty": 1, "gst_free": True}],
            "payment": {"method": "split", "card_cents": 500, "tendered_cents": 600}})["sale"]
        self.assertEqual(split["cash_cents"], 505)  # 507 rounds to 505
        self.assertEqual(split["total_cents"], 1005)
        self.assertEqual(split["change_cents"], 95)
        self.assertEqual(split["gst_cents"], 91)
        status, data = self.owner.call("POST", "/api/sales", {
            "items": [{"product_id": p["id"], "qty": 1}], "payment": {"method": "cash", "tendered_cents": 100}})
        self.assertEqual(status, 400)
        status, _ = self.owner.call("POST", "/api/sales", {"items": [], "payment": {"method": "card"}})
        self.assertEqual(status, 400)

    def test_stock_receive_and_count(self):
        p = self.product(stock=0)
        self.assertEqual(self.owner.ok("POST", "/api/stock/receive", {"product_id": p["id"], "qty": 12})["stock"], 12)
        r = self.owner.ok("POST", "/api/stock/count", {"product_id": p["id"], "counted": 9})
        self.assertEqual((r["stock"], r["change"]), (9, -3))
        moves = self.owner.ok("GET", f"/api/stock/moves?product_id={p['id']}")["moves"]
        self.assertEqual([m["reason"] for m in moves], ["stocktake", "receive"])

    def test_reports_and_cashup(self):
        p = self.product(price_cents=2000)
        self.owner.ok("POST", "/api/sales", {"items": [{"product_id": p["id"], "qty": 1}],
                                             "payment": {"method": "cash", "tendered_cents": 2000}})
        today = server.now_local().date().isoformat()
        rep = self.owner.ok("GET", f"/api/reports/summary?from={today}&to={today}")
        self.assertGreaterEqual(rep["totals"]["sale_count"], 1)
        self.assertIn("gross_profit_cents", rep["totals"])
        self.owner.ok("GET", "/api/reports/stock")
        cu = self.owner.ok("GET", "/api/cashup")
        r = self.owner.ok("POST", "/api/cashup", {"float_cents": 10000, "counted_cents": 10000 + cu["cash_sales_cents"]})
        self.assertEqual(r["diff_cents"], 0)
        status, body = self.owner.call("GET", "/api/backup", raw=True)
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"SQLite format 3"))

    def test_cashier_permissions(self):
        self.owner.ok("POST", "/api/users", {"name": "Casey", "role": "cashier", "pin": "5555"})
        uid = next(u["id"] for u in self.owner.ok("GET", "/api/users/public")["users"] if u["name"] == "Casey")
        cashier = Client(self.port)
        cashier.ok("POST", "/api/login", {"user_id": uid, "pin": "5555"})
        self.assertEqual(cashier.call("POST", "/api/products", {"name": "x", "price_cents": 1})[0], 403)
        self.assertEqual(cashier.call("GET", "/api/settings")[0], 403)
        self.assertNotIn("cost_cents", cashier.ok("GET", "/api/products")["products"][0])
        self.assertEqual(cashier.call("GET", "/api/reports/summary?from=2020-01-01&to=2020-01-31")[0], 403)
        # can't remove the last owner
        self.assertEqual(self.owner.call("PUT", f"/api/users/{self.owner_id}", {"role": "cashier"})[0], 400)

    def test_tag_link_redirect_and_setting(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("GET", "/t?c=P0001|MUG|14.95")
        r = c.getresponse()
        self.assertEqual(r.status, 302)
        self.assertEqual(r.getheader("Location"), "/scan.html?mode=count&code=P0001%7CMUG%7C14.95")
        self.assertEqual(self.owner.call("PUT", "/api/settings", {"tag_base_url": "not a url"})[0], 400)
        s = self.owner.ok("PUT", "/api/settings", {"tag_base_url": "https://192.168.1.20:8443/"})
        self.assertEqual(s["settings"]["tag_base_url"], "https://192.168.1.20:8443")

    def test_static_and_traversal(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("GET", "/")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        r.read()
        c.request("GET", "/../server.py")
        r = c.getresponse()
        self.assertEqual(r.status, 404)


if __name__ == "__main__":
    unittest.main()
