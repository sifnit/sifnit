# Product Camera

A phone camera web app for consistent product photos. It overlays your last shot, or any reference image, on the live view so you can line up the next product the same way. The overlay is only on screen; saved photos come straight from the camera.

## Run it from your computer

The camera only works over HTTPS, so `serve.py` runs a small HTTPS server with a self-signed certificate. It needs Python 3, plus either `pip install cryptography` or the `openssl` command.

```bash
cd product-camera
python3 serve.py
```

It prints an address like `https://192.168.1.20:8443`. Open that in Chrome on your phone, on the same Wi-Fi. Chrome warns that the connection isn't private because the certificate is self-signed: tap **Advanced**, then **Proceed**. Chrome remembers that choice for the address.

If your computer gets a new network address, the script makes a new certificate and you tap through the warning once more. On a self-signed certificate, Chrome won't install the app or cache it offline, but **Add to Home screen** still gives you an icon.

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
