# Lightweight Point-of-Sale (POS) — Plan

Status: **Phase 1 test version built** — see `pos/README.md`. Open questions are at the bottom.

## 1. What we're building

A small, easy-to-use point-of-sale and stock system for a staffed counter
(assisted checkout, **not** self-checkout):

- Runs in a web browser over **HTTPS (port 443)** — no app to install. Works on
  phones, tablets and a laptop/PC at the register.
- **Phones scan stock** with their camera (receiving, stocktake, price checks).
- **The register scans items placed on the bench** next to it, hands-free.
- **Printable stock tags** with barcodes, readable by phone cameras and scanners.
- **Payments:** cash, and credit/debit cards (provider: see section 6).
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
5. Receipt: printed (GST tax invoice, see 6a), or emailed / SMS / QR on request.
6. Refunds/returns by scanning or looking up the original sale.

Stock levels update automatically with every sale and refund.

## 6. Card payments (Australia)

**Key principle: our system never sees or stores card numbers.** The payment
provider handles the card, which keeps us out of the heavy card-security (PCI)
burden.

### Is PayPal the best choice? Probably not for in-person sales in Australia

PayPal's in-person card reader (Zettle) does not appear to be officially
available in Australia, and PayPal's Australian card fees are higher than the
in-person providers below. PayPal remains useful for **online** payments, but
for cards at the counter these are better fits — **no monthly fees, no lock-in**:

| Provider | In-person fee (approx., Oct 2026) | Monthly fee | Reader | Integrates with our POS? |
|---|---|---|---|---|
| **Square** | 1.6% flat (accounts opened after 30 May 2024) | None on free plan | Square Reader ~A$65 | Standalone with free Square app; full integration via Square Terminal + Terminal API |
| **Stripe Terminal** | ~1.65% + A$0.10 | None (A$15/mo only if a reader uses cellular data — not needed on shop Wi-Fi) | WisePad 3 from ~A$89; S700 smart reader ~A$449 | Yes — the POS sends the amount to the reader over the internet; built for custom systems like this one |
| PayPal | Higher than the above for cards | None | Zettle not confirmed in AU | QR / online checkout only |

*Rates change — confirm on each provider's Australian pricing page before signing up.*

### Recommended approach

| Stage | How it works |
|---|---|
| **Day one** | **Square Reader + free Square app**, used beside our POS. Cashier taps "Card" in our POS, charges on the reader, sale is recorded. Cheapest way to start: ~A$65 reader, 1.6% per sale, no monthly fee. |
| **Later (optional)** | **Fully integrated reader** — Stripe Terminal smart reader or Square Terminal. Our POS sends the exact amount to the reader; no re-keying, no mismatches. Decide once the shop is trading. |

## 6a. Australian specifics

- **GST 10%, prices include GST.** GST component on a receipt = total ÷ 11.
  GST-free items supported via a per-product flag.
- **Receipts are tax invoices:** business name, **ABN**, date, items,
  "Total price includes GST" and the GST amount. Sales over A$1,000 can also
  record the buyer's name/ABN.
- **Cash rounding:** cash totals round to the nearest 5c (no 1c/2c coins); card
  payments are charged to the exact cent. Rounding is tracked in reports.
- Currency AUD; dates DD/MM/YYYY; Australian timezone.
- Reports include a **GST summary** per period (sales, GST collected) to help
  with the BAS.

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

**Phase 1 — Trade with cash and card: BUILT (test version)**
- [x] Products, categories, auto SKUs, vendor codes, GST-free flag
- [x] QR tag printing (label printer sizes and A4 sheets)
- [x] Phone camera scanning and bench scanner support
- [x] Register: cash (5c rounding, change), card on a standalone reader, split
- [x] Receipts in tax-invoice format, refunds with restock
- [x] Reports: sales, cash vs card, GST, top sellers, low stock, stock value, activity log
- [x] Cash drawer end-of-day count
- [x] Receiving stock and stocktake from a phone, including from the phone's own
      camera app via tag links
- [x] HTTPS, owner/cashier PIN logins, backup download
- [ ] Trial in the shop with real hardware (phone, bench scanner, label printer)

**Phase 1b — Ordering (next)**
- Reorder list: everything at or below its alert level, grouped by vendor code
- Purchase orders: create, send (email or print), mark received. Receiving
  against an order fills in the expected quantities.
- Last cost price updated on receipt

**Phase 1c — Electronic shelf labels (ESL)**

Small e-ink price labels on the shelf edge that change price automatically when
the price changes in the POS. No reprinting tags.

- **How it fits:** ESLs sit on the shelf, not on the item. Items still carry
  their printed QR tag for scanning at the register. The ESL shows the shelf
  price and can show the same QR link, so phone stocktake works from the shelf too.
- **Pairing:** on a phone, scan the ESL's own barcode, then the product's QR tag,
  to link them. Unpair or move a label the same way.
- **What a label shows:** product name, price incl. GST, SKU / vendor code, QR
  link. Optional: "SALE" price with the was-price, low-stock flag for staff.
- **Updates:** any price, name or sale change in the POS is pushed to the label
  within seconds. Activity log records each push; a screen lists labels that
  failed to update (e.g. flat battery, out of range).
- **Coding approach:** an "ESL connector" inside the POS server. It watches
  product changes and sends them to the ESL system's base station or API. The
  connector is written per brand, so the brand can change later without
  touching the rest of the POS.
- **Before building — choose hardware:** compare ESL brands sold in Australia
  for (a) a **local base station with an open API** that works without the
  internet, (b) **no monthly cloud fee** (in line with avoiding EFTPOS-style
  rental fees), (c) cost per label and base station for about 100 products,
  (d) label size and battery life. Many ESL systems are cloud-subscription
  based, so this check matters.
- **Rollout:** start with a few labels on one shelf, then extend.

**Phase 1d — Hands-free counter scanning (camera + NFC)**

Goal: the customer puts items on the counter and they are added to the sale
without the cashier handling each one, whichever way up they are.

*Camera (overhead webcam on a stand)*
- QR codes read at any rotation, so upside down is fine. A tag that is
  **face down** can't be seen. Options for that: tags on two sides of the item,
  or a second camera looking up through a clear acrylic/glass window in the
  bench.
- Read **several items in one frame**. Today the camera takes one code at a time.
- Each code has its own "already counted" timer, so items resting on the bench
  are counted once and new items are added as they appear.
- **Identical items:** two identical mugs show identical QR codes, so the camera
  can't tell "two mugs" from "one mug seen twice". Fix: optional **per-unit
  serial** on tags (`P0001|MUG-BL|14.95|0007`) so each physical item is counted
  once. Without serials, the cashier taps + for extra identical items.
- Hardware: 1080p autofocus USB webcam on an arm, plus even lighting (a small
  LED panel) to avoid glare on glossy tags. Minimum tag QR size about 20 mm.

*NFC (reader pad on or under the bench)*
- An NFC sticker on each item (NTAG213/215, a few cents each in bulk) holds the
  same `SKU|VENDOR|PRICE` link as the QR code.
- Reads **any way up**, including face down, through packaging.
- Short range (about 1–4 cm) and **one item at a time**: the item is placed on
  the pad, beeps, and is moved aside. The pad can sit under a thin benchtop
  (test the thickness first) with a marked "tap here" spot.
- Metal items and liquids block NFC. These need "on-metal" tags or just use the
  QR code.
- **Works with the current software:** a USB NFC reader in keyboard mode types
  the tag contents plus Enter, the same as the bench barcode scanner.
- **Bonus:** phones with NFC (most iPhones and Android) can tap the tag to open
  the stocktake screen, the same as scanning the QR code.
- **Writing tags:** add "Write NFC tag" on the Products / Tags screen (works in
  Chrome on Android), or write them with a USB reader/writer.
- NFC tag IDs are unique per sticker, which also solves counting identical items.

*Combined disposable tags (QR printed on an NFC label)*
- Use **printable NFC labels**: a paper face with a thin NFC inlay (NTAG213)
  underneath, supplied on rolls. The label printer prints the QR code, name and
  price on top as usual. One sticker = QR + NFC, peeled off and thrown away like
  a normal price tag.
- **Printer check:** the roll must fit the label printer. Brother QL printers
  generally take Brother's own rolls only, so NFC rolls usually suit a generic
  direct-thermal label printer that accepts third-party rolls (e.g. 50 × 30 mm).
  Test that the printer feeds and prints cleanly over the inlay bump before
  buying in bulk.
- **Encoding (writing the NFC part) after printing**, in the POS:
  1. Print a batch of tags as now.
  2. Tags screen → **Encode NFC**: the screen shows the first tag in the batch.
  3. Hold that printed tag to the writer. The POS writes the same link as the
     QR code, reads it back to check, records the tag's unique ID, and moves to
     the next tag.
- **Writer options:**
  - *Android phone in Chrome* (Web NFC): no extra hardware. Fine for the test
    and for about 100 products. iPhones can't write from a web page.
  - *USB NFC reader/writer at the bench* (PC/SC type, e.g. ACR122U class): the
    POS server talks to it directly. Faster for big batches, but needs one extra
    Python package on the POS computer.
- **Mismatch guard:** because the POS writes the NFC chip from the same data as
  the printed QR code, they can't disagree. If a tag's NFC and QR are ever
  scanned and don't match, the register warns.
- **Later option:** printers that print and encode in one pass exist, but cost
  much more. Only worth it at high volume.
- **Reading at the register: use the tag's unique ID (UID).** Most cheap USB
  "keyboard mode" NFC readers type only the tag's UID, not the link stored on
  it. The Encode NFC step therefore records each tag's UID against the product,
  and the register looks up UIDs as well as QR codes. Any keyboard-mode reader
  then works with no extra software, and identical items are counted
  separately because every UID is different.
- **Hardware options:**
  | Role | Option | Rough AU price | Notes |
  |---|---|---|---|
  | Print | TSC DA210 (direct thermal only) | to quote | No ribbon needed; enough for paper NFC labels |
  | Print | TSC TE210 (direct thermal + transfer) | A$424–732 | Ribbon optional; Ethernet/Wi-Fi models |
  | Write tags | Android phone, Chrome | A$0 if owned | Web NFC; simplest for ~100 products |
  | Write tags | ACS ACR122U USB | ~A$80 | Needs a small helper on the POS computer |
  | Read at bench | USB NFC reader, keyboard mode (UID) | ~A$30–80 | Plug-and-play with the register via UID lookup |
  | Read at bench | ACS ACR122U (PC/SC) | ~A$80 | Reads UID and link; same helper as writing |
- **Media cost (rough, Oct 2026, confirm with AU suppliers):** plain direct
  thermal labels about **3–4c each** (e.g. A$17 inc GST per 500 × 50×25 mm);
  printable NTAG213 NFC labels about **A$0.30–0.45 each** in rolls of
  1,500–4,500 from overseas web stores (USD 0.20–0.30) plus shipping, or
  about **A$0.12–0.20** in 10,000+ bulk imports. So NFC adds roughly 10× to tag
  cost. Use NFC tags only for items that often land face down or are
  awkward to scan, and plain QR tags for the rest.
- **TSC desktop printers** (e.g. TE200/TE210/DA220 class, direct thermal) take
  generic third-party label rolls, so they suit printable NFC labels. They print
  only. The NFC chip is written in the separate Encode NFC step. Most TSC "R"
  (RFID) models are **UHF**, which is not NFC. TSC's HF/NFC encoding options are
  limited (e.g. a kit for the DH220 healthcare series), and NTAG support isn't
  confirmed, so they're not needed for this.

*Large and bulky items*
- NFC range is only about 1–4 cm whatever the item size, so it's the **tag**
  that has to reach the pad, not the item.
- **Tag placement rule:** small items get the tag on the base (put down = read);
  large items get the tag where it can be presented, or a **swing tag** on a
  string or loop (QR + NFC label folded over card) that can be lifted to the pad.
- **Too heavy to lift:** use a **handheld** instead of moving the item: a
  cordless 2D barcode scanner (reads the QR from 10–50 cm) or a phone with the
  register page open. Both feed the same sale.
- **Overhead camera** reads large items fine when the tag faces up or sideways.
- Fallback for anything awkward: search by name at the register.

*Not recommended for now:* UHF RFID reads a whole basket at once from a
distance, but readers and setup cost far more than a small shop needs.

*Recommendation:* both. Overhead camera for most items, plus an NFC pad for
face-down, curved or small items. Trial each at the counter before buying in
bulk.

**Phase 2 — Integrated card payments (optional)**
- Integrated card reader (Stripe Terminal or Square Terminal)
- Payment reconciliation report: POS card totals vs provider payouts

**Phase 3 — Polish**
- CSV export for the accountant / BAS
- Emailed/SMS receipts
- Part refunds (single items)
- PayPal for online orders, if ever needed
- Offline queue for cloud hosting if chosen

## 12. Decisions so far

- Single shop in **Australia**, AUD, **GST 10% included** in prices.
- Has a **label printer**; customers get **receipts**.
- Goal: **avoid monthly EFTPOS terminal rental fees** from the bank.
- Card provider: decision pending — Square suggested to start (section 6).

- About **100 products**, no existing barcodes: every product gets a small
  **QR tag** holding `SKU|VENDOR|PRICE`.
- First build is a test version with no shop branding. Name, ABN and address
  are entered later in Settings.
- Built with only the Python standard library and SQLite, so it runs on a
  Raspberry Pi or mini PC.

- Phone camera stocktake: scanning a tag with the phone's normal camera opens
  the stocktake screen (see `docs/OPERATIONS.md`).

## 13. Remaining questions

1. **Label printer make/model**, to fine-tune the tag templates. Should receipts
   print on it, or on a separate receipt printer?
2. **Hosting:** box in the shop (recommended) or cloud?
3. Should **cashiers** be allowed to apply stocktake counts, or owners only?
4. Do you want **purchase orders** in the system (Phase 1b), or keep ordering by
   phone/email with just a reorder list?
5. **ESL:** labels on every shelf position, or only for selected products?
   Do you already have an ESL brand in mind?
6. **Counter scanning:** what is the benchtop made of and how thick is it (for an
   under-bench NFC pad)? Do customers usually put down many identical items at
   once?
