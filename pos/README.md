# POS – test version

A lightweight point-of-sale and stock system for one shop. It runs in a web
browser over HTTPS, so there's nothing to install on phones or the register.

- **Register** for an assisted checkout: scan items on the bench, take cash, card or split payment, and get exact change with 5c cash rounding.
- **Phone scanning** for price checks, receiving stock and stocktakes.
- **QR stock tags** holding `SKU|VENDOR|PRICE`, printed on a label printer or A4 sheet labels.
- **Reports on screen**: sales, cash vs card, GST collected, top sellers, low stock, stock value, cash drawer count and an activity log.
- **Receipts** shown on screen or printed (58, 62 or 80 mm). They become a "Tax invoice" once an ABN is entered.
- **Owner and cashier logins** with PINs.

This is a test version: the shop name, ABN and address are left blank and set in **Settings**.

## Requirements

- **Python 3.9 or newer**, with no extra packages. This works on a Raspberry Pi, a mini PC, a Mac or Linux.
- **`openssl`**, which is only used to create the test certificate.

## Quick start

```bash
cd pos
python3 seed_demo.py               # optional: adds 10 sample products
sudo python3 server.py             # serves https://<this-computer's-IP>/ on port 443
# or, without sudo:
python3 server.py --port 8443      # https://<IP>:8443/
```

The server prints the address to open. Log in as **Owner** with PIN **1234**,
then change the PIN in **Settings**.

### Phones and the certificate

On first run the server makes a **self-signed certificate** in `data/`. Phones
show a warning the first time; tap *Advanced → Proceed*. The camera needs HTTPS,
and it works after you accept the warning.

For a permanent set-up without the warning, use a real certificate. Either:
- run `server.py --http --host 127.0.0.1 --port 8080` behind **Caddy** (see `Caddyfile.example`), or
- pass your own certificate with `--cert fullchain.pem --key privkey.pem`.

## Everyday use

| Task | Where |
|---|---|
| Add a product, set its price and vendor code | **Products → Add product**. Leave the SKU blank to auto-number it (P0001…). |
| Print tags | **Tags**, or tick products in **Products → Print tags for selected**. Pick the label size, then print. In the print dialog use your label printer, the same paper size, 100% scale and no margins. |
| Sell | **Register**. Scan with the bench scanner or camera, or type a name. Then **Pay → Cash / Card / Split**. |
| Card payments | Charge the amount on your separate card reader (e.g. Square), then tap **Approved** in the POS. |
| Refund | Open the sale (Reports → Sales, or the receipt link) and tap **Refund this sale**. Owner only. The items go back into stock. |
| Receive stock | On a phone: **Scan stock → Receive**. Scan each item, adjust the quantities, then **Add to stock**. |
| Stocktake | **Scan stock → Stocktake**. Scan everything on the shelf, check the differences, then **Apply counts**. Owner only. |
| End of day | **Reports → Cash drawer**. Enter the float and the cash counted to see if the drawer is over or short, then save. |
| Backup | **Settings → Download backup**. You can also copy `data/pos.db` while the server is stopped. |

### Scanners

- **Bench scanner (recommended):** any USB or Bluetooth 2D/QR "presentation"
  scanner in keyboard mode. You don't need to click anything first. It must be
  a **2D** scanner, because 1D-only laser scanners can't read QR codes.
- **Camera:** tap **Camera** on the Register or Scan stock page. An item sitting
  in view is read once; move it away for about 1.5 seconds before scanning the
  same item again.

### Tags

Each QR code holds `SKU|VENDOR|PRICE`, for example `P0001|MUG-BL|14.95`. The
system always charges the **current price**. If a tag's printed price is out of
date, the register warns you to reprint it.

## Tests

```bash
cd pos
python3 -m unittest discover tests
```

## Files

```
pos/
  server.py        HTTPS server, API and database (standard library only)
  seed_demo.py     sample products
  static/          the web pages (register, scan, products, tags, reports, settings)
  static/vendor/   qrcode-generator (MIT) and jsQR (Apache-2.0)
  data/            created on first run: pos.db, cert.pem, key.pem (not committed)
```
