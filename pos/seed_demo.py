#!/usr/bin/env python3
"""Add sample products so the system can be tried out. Run once: python3 seed_demo.py"""
import server

DEMO = [
    # name, vendor code, category, price, cost, stock, reorder
    ("Coffee Mug - Blue", "MUG-BL", "Kitchen", 14.95, 6.00, 12, 4),
    ("Coffee Mug - Red", "MUG-RD", "Kitchen", 14.95, 6.00, 8, 4),
    ("Tea Towel Set", "TT-3", "Kitchen", 19.50, 8.20, 6, 3),
    ("Scented Candle Large", "CN-L", "Home", 32.00, 13.50, 5, 2),
    ("Scented Candle Small", "CN-S", "Home", 12.00, 4.80, 20, 5),
    ("Greeting Card", "GC-01", "Cards", 6.95, 2.10, 40, 10),
    ("Wrapping Paper Roll", "WP-R", "Cards", 4.50, 1.20, 2, 5),
    ("Notebook A5", "NB-A5", "Stationery", 9.95, 3.40, 15, 5),
    ("Ballpoint Pen 3pk", "PEN-3", "Stationery", 5.00, 1.60, 30, 10),
    ("Local Honey 500g", "HNY-500", "Food", 12.50, 7.00, 10, 4),
]


def main():
    server.init_db()
    conn = server.connect()
    now = server.ts(conn)
    added = 0
    for name, vendor, cat, price, cost, stock, reorder in DEMO:
        if conn.execute("SELECT 1 FROM products WHERE name=?", (name,)).fetchone():
            continue
        cur = conn.execute(
            "INSERT INTO products (sku, name, vendor_code, category, price_cents, cost_cents, stock, "
            "reorder_level, gst_free, updated_at) VALUES ('TMP', ?,?,?,?,?,?,?,?,?)",
            (name, vendor, cat, round(price * 100), round(cost * 100), stock, reorder,
             1 if cat == "Food" else 0, now))
        conn.execute("UPDATE products SET sku=? WHERE id=?", (f"P{cur.lastrowid:04d}", cur.lastrowid))
        conn.execute(
            "INSERT INTO stock_moves (created_at, product_id, qty_change, reason) VALUES (?,?,?, 'initial')",
            (now, cur.lastrowid, stock))
        added += 1
    conn.commit()
    print(f"Added {added} demo products.")


if __name__ == "__main__":
    main()
