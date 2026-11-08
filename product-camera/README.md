# Product Camera

A phone camera web app for consistent product photos. It overlays your last shot, or any reference image, on the live view so you can line up the next product the same way. The overlay is only on screen; saved photos come straight from the camera.

## Run it from your PC

The PC serves the app to your phone, and finishes every photo you take:

- cuts the item out, with a light feather on the edge
- centres it on a white 1000 × 1000 square with a small white border
- names it after the object and the date: `blue-mug_2026-11-09.jpg`, then `_2`, `_3` for more that day

The object name is the **Set** name at the top of the camera app. The date comes from the photo.

**One-time setup** (Python 3.10 to 3.13):

```
cd product-camera
pip install -r requirements.txt
```

**Each time:**

```
python serve.py
```

The first start downloads the cutout model (about 900 MB). It prints an address like `https://192.168.1.20:8443`. Open that in Chrome on your phone, on the same Wi-Fi. Chrome warns that the connection isn't private because the certificate is self-signed: tap **Advanced**, then **Proceed**. On Windows, allow Python through the firewall for **Private networks** when asked.

Photos land in `product-camera/photos/`:

- `finished/`: the 1000 × 1000 white-background images
- `originals/`: the untouched photos from the phone

To save somewhere else: `python serve.py --out D:\Listings`

The chip at the top of the app shows the PC's progress; tap it for details. If the phone can't reach the PC, photos stay on the phone, and **Photos → Send to PC** sends them later.

Each photo takes 20 to 30 seconds on the PC and uses about 8 GB of memory while it works. PCs with less than 12 GB of RAM automatically use a lighter cutout model, which is fast but slightly less precise on edges.

**Photos already on the PC:** `python process.py some-folder --name blue-mug` finishes every photo in a folder the same way.

## Use it

1. Open the app in Chrome on your phone and tap **Start camera**.
2. Take the first photo. It becomes the reference automatically.
3. Pick **Ghost** (faded previous photo) or **Outline** (just the product's edge), and set the strength with the slider.
4. Put the next product in place, line it up, shoot. Each photo becomes the next reference, so you can turn that off from the reference button to keep one master shot.
5. Tap **Photos**, then **Download all** or **Share all**.

## Tips

- **Lock** (top right, on phones that support it) holds focus, exposure and white balance, so every shot in a set matches. Set up the first shot, tap Lock, then shoot the rest.
- **Grid** adds thirds and a centre cross.
- **Set** names the files: `mug-001.jpg`, `mug-002.jpg` and so on.
- For the cleanest outline, load a transparent PNG cutout as the reference (from the `remove-background-local` skill). On a plain backdrop the app traces the product itself.
- Photos and the reference are kept on the phone between visits until you delete them.
- In Chrome's menu, **Add to Home screen** installs it like an app.
