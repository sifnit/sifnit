# POS Operations Guide

How stock moves through the shop, from ordering to sale, and how to do a
stocktake. Setup and install steps are in `pos/README.md`.

## 1. Order in → sale

| # | Step | Where | Status |
|---|---|---|---|
| 1 | **Spot what's running low.** Products at or below their alert level are listed. | Reports → Low stock | Built |
| 2 | **Order from the supplier.** For now this is done by phone or email; the vendor code on each product helps when ordering. | Outside the POS | Planned: purchase orders |
| 3 | **Add any new products.** Name, price incl. GST, vendor code, cost and alert level. The SKU numbers itself (P0001…). | Products → Add product | Built |
| 4 | **Receive the delivery.** On a phone, scan each item; each scan adds 1. Adjust the quantities and add the invoice number as a note. | Scan stock → Receive | Built |
| 5 | **Print tags** for new items or changed prices. | Tags, or Products → Print tags for selected | Built |
| 6 | **Tag and shelve.** | — | — |
| 7 | **Customer brings items to the counter.** Each item is placed under the bench scanner, or scanned by camera or looked up by name. | Register | Built |
| 8 | **Take payment.** Cash with change (rounded to 5c), card on the separate reader then tap Approved, or split. | Register → Pay | Built |
| 9 | **Receipt** printed or shown on screen (tax invoice once the ABN is set). | Receipt | Built |
| 10 | **Stock comes off automatically.** Reports, GST totals and low-stock alerts update straight away. | Automatic | Built |
| 11 | **End of day:** count the drawer against expected cash. | Reports → Cash drawer | Built |
| 12 | **Stocktake** regularly to correct for breakage, loss and mistakes. | Scan stock → Stocktake | Built |

Then back to step 1.

Refunds go the other way: open the sale, **Refund this sale** (owner), and the
items go back into stock.

## 2. Stocktake

### One-time setup
1. On a phone connected to the shop Wi-Fi, log in as an owner.
2. **Settings → Tag web address → Use this address → Save.**
3. Give the POS computer a **fixed IP address** in your router (a "DHCP
   reservation"), so the address on the tags never changes.
4. **Reprint all tags** (Tags → Add all products → Print). The QR codes now
   contain a link as well as the SKU, vendor code and price.

### Counting with the phone's own camera (no app needed)
1. Open the phone's normal camera and point it at a tag.
2. Tap the link that appears. The **Stocktake** screen opens with that product
   at the top and the count box selected.
3. Type how many are on the shelf. The difference shows straight away:
   **OK** matches, **+2** = more than the system thinks, **−3** = fewer.
4. Scan the next tag. It joins the same list, even in a new tab.
5. When the shelf or section is done, tap **Apply counts**.

### Counting with the in-app camera
**Scan stock → Stocktake → Scan with camera.** Each scan of a tag adds 1, so
you can scan every item one by one. You can still type over any number.

### What happens when counts are applied
- Each product's stock is set to the counted number.
- The change is recorded in that product's **Stock history** (Products → product
  → Stock history) as *stocktake*, with who did it and when.
- Products whose count matched are not changed.

### Tips
- Count one shelf or section at a time and apply it, rather than the whole shop
  at once.
- Count before opening or after closing. A sale made between scanning and
  applying will make that product's count look one short.
- Items you can't find have no tag to scan. Look them up in **Products** and
  correct them later, or type the SKU into the box under the camera.
- The list is kept on that phone until you apply or clear it.

### Who can do it
Anyone can scan and count. Only an **owner** can apply the counts.

### Troubleshooting
| Problem | Fix |
|---|---|
| Phone shows a security warning | Expected with the test certificate. Tap *Advanced → Proceed* once. |
| Link won't open / "can't reach" | Phone must be on the shop Wi-Fi, and the POS computer must be running. |
| Opens the wrong address | The POS computer's IP changed. Fix it in the router, update Settings, reprint tags. |
| Camera shows only text, no link | Tag was printed before the tag web address was set. Reprint it. |
| "Only an owner can apply" | Log in as an owner on that phone, or ask the owner to apply. |
