# Lightweight Point-of-Sale (POS) — Plan

Status: **draft plan, not yet built.** Open questions are at the bottom.

## 1. What we're building

A small, easy-to-use point-of-sale and stock system for a staffed counter
(assisted checkout, **not** self-checkout):

- Runs in a web browser over **HTTPS (port 443)** — no app to install. Works on
  phones, tablets and a laptop/PC at the register.
- **Phones scan stock** with their camera (receiving, stocktake, price checks).
- **The register scans items placed on the bench** next to it, hands-free.
- **Printable stock tags** with barcodes, readable by phone cameras and scanners.
- **Payments:** cash, and credit/debit cards via **PayPal**.
- **Reports live on screen** — no printing needed (export to CSV only if wanted).
- Light enough to run on a mini PC / Raspberry Pi in the shop, or a small
  cloud server.

## 2. How it fits together

```
 [Phone (camera)] ─┐
 [Tablet/PC at     ├── HTTPS :443 ──> [Caddy (TLS)] ──> [POS app] ──> [SQLite DB]
  register + bench │                                        │
  scanner]        ─┘                                        └──> PayPal API (cards)
```

- **One server process + one database file.** Easy to back up (copy one file),
  easy to run, nothing heavy to maintain.
- **Caddy** in front handles HTTPS certificates automatically (Let's Encrypt).
  HTTPS isn't optional: phone browsers only allow camera access on secure pages.
- **Suggested stack:** Python (FastAPI) + SQLite + a plain HTML/JS front end
  installed as a PWA ("Add to home screen"). Big buttons, minimal typing.

## 3. Scanning

| Where | How | Notes |
|---|---|---|
| Phone (stock work) | Browser camera; native `BarcodeDetector` with a ZXing JS fallback | Beep + vibrate on read, continuous mode for stocktake |
| Register bench | **Hands-free "presentation" barcode scanner** (USB/Bluetooth, ~$40–100) | Most robust option. Acts like a keyboard — no drivers, no integration. Item is placed under it and reads automatically |
| Register bench (zero-cost option) | Old phone or webcam on a stand, running the scan page in continuous mode | Works, but slower and more lighting-sensitive than a dedicated scanner |

The register screen always has an "add by search / tap" fallback for items
without tags.

## 4. Stock tags

- Each product gets an internal SKU. If it already has a manufacturer barcode
  (UPC/EAN), we use that instead — no tag needed.
- Tags show: **barcode (Code 128)**, product name, price, SKU in plain text.
  Optional **QR code** for very small or curved items.
- Printing straight from the browser, with templates for:
  - sheet labels on a normal printer (e.g. Avery-style A4/Letter sheets), and
  - thermal label printers (Brother QL / Dymo / Zebra sizes).
- Print one tag, a quantity on receipt of stock, or "all items changed since…".

## 5. Selling (assisted checkout)

1. Cashier logs in with a quick PIN.
2. Items are scanned on the bench (or by phone/handheld) → added to the cart.
   Same item scanned again = qty +1. Edit qty, remove, discount (with permission).
3. Choose payment: **Cash**, **Card (PayPal)**, or **Split**.
4. Cash: enter amount tendered → big on-screen "Change due".
5. Receipt: on screen by default; optional email/SMS link or QR the customer can
   scan. (Printed receipts optional later.)
6. Refunds/returns by scanning or looking up the original sale.

Stock levels update automatically with every sale and refund.

## 6. Card payments via PayPal

**Key principle: our system never sees or stores card numbers.** PayPal handles
the card, which keeps us out of the heavy card-security (PCI) burden.

Three ways to take cards, simplest first:

| Option | How it works | Effort |
|---|---|---|
| **A. Standalone card reader, recorded manually** | Use PayPal's in-person card reader (PayPal Zettle, where available in your country) with its own app. Cashier taps "Card" in our POS, enters/confirms the PayPal reference. | Low — works on day one |
| **B. QR pay-on-phone** | POS creates a PayPal order via the PayPal API and shows a QR code. Customer scans it and pays with PayPal or **any credit/debit card as a guest**. POS gets confirmation automatically and completes the sale. | Medium |
| **C. Fully integrated card reader** | POS sends the amount to the reader automatically. | Depends on what PayPal currently offers in your country — to be confirmed |

**Recommendation:** start with **A + cash** so the shop can trade immediately,
add **B** in phase 2. Investigate **C** once we confirm the country/region.

## 7. On-screen reports

Dashboard designed for a screen, not paper — big numbers, simple charts, tap to
drill down:

- **Today at a glance:** sales total, number of sales, average sale, cash vs card.
- **Cash drawer / end-of-day:** opening float + cash sales − cash refunds =
  expected cash; enter counted cash → shows over/short. Saved per day.
- **Sales by period:** day / week / month / custom range, by product, category,
  cashier, payment type.
- **Top sellers and slow movers.**
- **Stock:** current levels, **low-stock alerts**, stock value (cost and retail),
  stock movement history per item.
- **Audit log:** voids, refunds, discounts, price changes, stock adjustments —
  who and when.
- Optional CSV export for an accountant.

## 8. Stock management (mostly on phones)

- **Add product:** scan existing barcode or generate an SKU, enter name, price,
  cost, category, reorder level; print tag.
- **Receive stock:** scan → enter qty → done. Optionally print tags for the batch.
- **Stocktake mode:** scan everything on a shelf; system compares to expected and
  shows differences before you accept.
- **Adjustments** with a reason (damaged, lost, used in-store).

## 9. Users & security

- Roles: **Owner** (everything), **Cashier** (sell, cash drawer, view today).
- PIN login at the register; full password for owners/remote access.
- HTTPS everywhere, sessions time out, all sensitive actions logged.
- Automatic nightly backup of the database file (local + off-site copy).

## 10. Hosting choice

| | Shop mini PC / Raspberry Pi | Small cloud server |
|---|---|---|
| Internet goes down | Cash sales and scanning keep working on the shop Wi-Fi; only card payments stop | Everything stops (unless we add an offline queue) |
| Access from home | Needs a secure tunnel (e.g. Tailscale / Cloudflare Tunnel) | Built in |
| HTTPS certificate | Via DNS challenge or tunnel | Automatic |
| Cost | One-off hardware | Small monthly fee |

**Recommendation:** a box in the shop plus a secure tunnel for remote reports.

## 11. Phased delivery

**Phase 1 — Trade with cash (MVP)**
- Products, categories, SKUs, tag printing
- Phone camera scanning + bench scanner support
- Register screen, cash sales, change calculation, refunds
- Card sales recorded manually (option A)
- Today dashboard, cash drawer end-of-day, low stock
- HTTPS deployment, users/PINs, backups

**Phase 2 — PayPal integration**
- PayPal QR payments (option B) with automatic confirmation (webhooks)
- Payment reconciliation report: POS card totals vs PayPal

**Phase 3 — Polish**
- Full report set, stocktake mode, CSV export
- Emailed/SMS receipts
- Integrated card reader (option C) if available
- Offline queue for cloud hosting if chosen

## 12. Open questions

1. **Country/currency?** Decides which PayPal card products are available and
   how sales tax/VAT/GST is shown.
2. **Hosting:** box in the shop, or cloud?
3. **Roughly how many products** and **how many registers/staff?**
4. Do most products already have **manufacturer barcodes**, or will most need tags?
5. **Label printer:** do you have one, or plain sheet labels on a normal printer?
6. Do customers need **receipts** (paper, email, SMS, or none)?
7. Do prices **include tax**, and are there different tax rates?
8. Do you already have a **PayPal Business account**?
