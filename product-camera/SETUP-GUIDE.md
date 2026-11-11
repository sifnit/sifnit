# Product Camera: Setup Guide

Product Camera turns a phone and a PC into a simple product photo station.

- **On the phone:** a camera app that shows your last shot as a faded "ghost" or an outline over the live view, so every product is framed the same way. The overlay is only on screen and never appears in the photos.
- **On the PC:** every photo you take is sent to the PC and finished automatically: the item is cut out with softened edges, centred on a white 1000 × 1000 square with a small white border, and saved as `<object>_<date>.jpg`, for example `blue-mug_2026-11-11.jpg`.

Everything runs on your own PC and phone. There are no accounts or subscriptions, and photos never leave your network.

Setup takes about 15 minutes, plus a one-time 900 MB download.

---

## What you need

| | |
|---|---|
| **PC** | Windows, Mac or Linux. 16 GB of RAM is recommended; with less than 12 GB it uses a lighter, slightly less precise cutout. About 2 GB of free disk space. |
| **Phone** | Android with Chrome. |
| **Network** | Phone and PC on the **same Wi-Fi**. Guest networks often block devices from seeing each other, so use the main one. |
| **Python** | Version 3.10, 3.11, 3.12 or 3.13. 3.12 is the safest choice. |

---

## 1. Install Python (skip if you have it)

**Windows**

1. Download Python 3.12 from <https://www.python.org/downloads/windows/>. Choose the "Windows installer (64-bit)".
2. Run it. On the first screen, **tick "Add python.exe to PATH"**, then click **Install Now**.
3. Open **Command Prompt** and check it worked:
   ```
   python --version
   ```
   It should print `Python 3.12.x`.

**Mac:** install from <https://www.python.org/downloads/macos/>, then use `python3` and `pip3` wherever this guide says `python` and `pip`.

---

## 2. Get the files

The code is in a public GitHub repository: <https://github.com/sifnit/sifnit>, on the branch `ccr-ab7f6d1c-gk6wtp`.

**Easiest: download a ZIP**

1. Open <https://github.com/sifnit/sifnit/tree/ccr-ab7f6d1c-gk6wtp>
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip it somewhere easy, such as `C:\ProductCamera`.
4. Inside, find the **`product-camera`** folder. That's the only part you need.

**Or with git:**
```
git clone -b ccr-ab7f6d1c-gk6wtp https://github.com/sifnit/sifnit.git
```

The `product-camera` folder should contain `index.html`, `serve.py`, `process.py`, `requirements.txt` and a few small files.

---

## 3. Install what it needs (one time)

Open Command Prompt (or Terminal on Mac) and go to the `product-camera` folder. For example:

```
cd C:\ProductCamera\sifnit-ccr-ab7f6d1c-gk6wtp\product-camera
pip install -r requirements.txt
```

This installs the cutout engine and takes a few minutes. If Windows says `pip` isn't recognised, use `py -m pip install -r requirements.txt` instead.

---

## 4. Start it

From the same folder:

```
python serve.py
```

The first start downloads the cutout model (about 900 MB) and shows progress. After that it starts in a few seconds. When it's ready you'll see something like:

```
Product Camera is running.

  On your phone, open:  https://192.168.1.20:8443

  Finished photos:  C:\...\product-camera\photos\finished
  Originals:        C:\...\product-camera\photos\originals

Cutout model loaded. Ready for photos.
```

**Windows firewall:** the first time, Windows asks whether to allow Python on the network. Tick **Private networks** and click **Allow**. If you miss it, see Troubleshooting.

Leave this window open while you shoot. Close it, or press `Ctrl+C`, to stop.

---

## 5. Connect the phone

1. On the phone, open **Chrome** and type the address the PC printed, including `https://` and `:8443`.
2. Chrome warns **"Your connection is not private"**. This is expected: the PC makes its own security certificate, which Chrome doesn't recognise. Tap **Advanced**, then **Proceed to … (unsafe)**. Chrome remembers this for that address.
3. Tap **Start camera** and allow camera access.
4. A chip at the top should say **PC ready**. That means the phone can reach the PC.
5. Optional: Chrome menu (⋮) → **Add to Home screen** to give it an app icon.

---

## 6. Shooting

1. Type the product name in the **Set** box at the top, for example `blue mug`. This becomes the file name.
2. Set up the product and take the first photo. It becomes the reference.
3. Choose **Ghost** (faded last photo) or **Outline** (just the product's edge), and adjust the strength with the slider.
4. Place the next item so it lines up with the overlay, then shoot. Each photo becomes the reference for the next one; turn that off from the **Reference** button to keep one master shot.
5. Change the **Set** name whenever you move to a different product.

**For matching photos:**

- Use a phone stand or tripod, and keep the lighting the same.
- After framing the first shot, tap **Lock** (top right) to hold focus, exposure and white balance for the rest of the set. Lock only appears on phones that support it.
- **Grid** adds thirds and a centre cross.

**Where the photos go:**

| Folder on the PC | Contents |
|---|---|
| `photos\finished\` | 1000 × 1000 white-background images, named `blue-mug_2026-11-11.jpg`, then `_2`, `_3` for more that day |
| `photos\originals\` | The untouched photos from the phone |

Each photo takes about 20 to 30 seconds to finish on the PC; it works through them in the background while you keep shooting. The chip at the top shows progress, and tapping it shows details.

If the PC can't be reached, photos stay safely on the phone. Open **Photos → Send to PC** once it's back.

---

## Other things it can do

**Save finished photos somewhere else**
```
python serve.py --out D:\Listings
```

**Finish photos already on the PC** (from another camera, for example)
```
python process.py "C:\path\to\folder" --name blue-mug
```
Results go to a `finished` folder; add `--out` to choose another.

**Change the size, border or edge softness:** open `process.py` in Notepad. Near the top:
```
SIZE = 1000         # output is SIZE x SIZE
MARGIN = 50         # white border on each side
FEATHER = 2.0       # light edge softening, in pixels
```
Change the numbers, save, and restart `serve.py`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Phone shows "This site can't be reached" | Check both are on the same Wi-Fi, and not a guest network. Check `serve.py` is still running. Allow Python through the firewall: Windows Security → **Firewall & network protection** → **Allow an app through firewall** → tick **Private** for Python. |
| The address stopped working | The PC got a new network address. Look at the address `serve.py` prints now, and tap through the certificate warning once more. |
| Camera won't start | Tap the icon left of the address in Chrome → **Permissions** → allow **Camera**. Close other apps using the camera. |
| Chip says **PC offline** | The phone can't reach the PC: see the first row. Photos taken meanwhile are kept on the phone. |
| Chip says **PC error** | The cutout engine didn't install properly. Run `pip install -r requirements.txt` again and read any error it shows. |
| `pip` or `python` "is not recognized" | Reinstall Python with **Add python.exe to PATH** ticked, or use `py` instead of `python` and `py -m pip` instead of `pip`. |
| Install fails mentioning `onnxruntime` | Your Python is too new or too old. Install Python 3.12 and try again. |
| Model download stops partway | Delete the `.u2net` folder in your user folder (for example `C:\Users\<you>\.u2net`) and start `serve.py` again. |
| Startup says it's using the lighter model | The PC has less than 12 GB of RAM. It still works, but edges are slightly less precise. |
| An item isn't fully cut out | A plain backdrop that contrasts with the product, and even lighting, give the cleanest cutouts. |

---

## Good to know

- **Privacy:** nothing is uploaded to the internet. The only download is the one-time cutout model.
- **The "not private" warning** is only because the PC signs its own certificate. The connection is still encrypted, and it only works on your local network.
- **Photos stay on the phone too,** until you delete them from **Photos** in the app.
