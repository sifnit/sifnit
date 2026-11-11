# Build Product Camera with Claude

**How to use this file:** open Claude Code (or a Claude chat with file access) in an empty folder on the PC that will run this, and paste or attach this whole file with the message:

> Build this for me. Follow the spec, then walk me through starting it and connecting my phone.

Everything below is written to Claude.

---

## What you're building

A free, local product photo station made of two parts that work together. No accounts, no paid APIs, no cloud services. Photos must never leave the user's network.

1. **A phone camera web app** (Android Chrome) that overlays the previous photo on the live camera view, as a faded "ghost" or as an outline of the product, so every product in a set is framed identically. The overlay is shown on screen only and must never appear in a saved photo.
2. **A Python program on the PC** that serves the app to the phone over HTTPS on the local Wi-Fi, receives each photo as it's taken, and turns it into a finished listing image.

Each finished image must be:

- the product cut out from its background, with a light feather (about 2 px) on the edge to soften jaggies
- centred on a **white 1000 × 1000** square with a **50 px** white border on each side (the item fits within 900 × 900, keeping its proportions)
- saved as JPEG named **`<object>_<YYYY-MM-DD>.jpg`**, then `_2`, `_3` … for more of the same object on the same day. The object name is typed in the app; the date is when the photo was taken.

Keep the originals as well.

## Files to create

Put everything in one folder, `product-camera/`:

| File | Purpose |
|---|---|
| `index.html` | The whole phone app: one file, inline CSS and JS, no frameworks, no CDN |
| `manifest.webmanifest`, `icon.svg`, `sw.js` | Add-to-home-screen support and a network-first service worker that skips `/api/` |
| `serve.py` | HTTPS server, self-signed certificate, upload endpoint, background processing queue |
| `process.py` | The cutout and finishing step; also usable on its own on a folder of photos |
| `requirements.txt` | `rembg[cpu]`, `pillow`, `cryptography` |
| `README.md` | Short user guide: install, start, connect the phone, troubleshooting |

## Phone app: `index.html`

Make it look and feel like a native camera app: dark, full-bleed viewfinder, controls at the bottom, safe-area insets respected.

**Camera**

- `getUserMedia` with the rear camera (`facingMode: environment`), asking for the highest resolution at a 4:3 aspect ratio.
- Show the video with `object-fit: contain` behaviour, meaning the whole frame with letterboxing, so what the user sees is what is captured. Size the overlay canvas to exactly the displayed video rectangle.
- If camera permission was already granted (check `navigator.permissions`), start automatically; otherwise show a **Start camera** button. Show clear messages for blocked permission and for a missing secure context.
- Request a screen wake lock while it's open.

**Overlay: Off / Ghost / Outline**

- **Ghost:** the reference image drawn over the live view with an opacity slider (10–90 %, default 35 %).
- **Outline:** the reference subject's outline in a bright teal (`#39e5c4`) with a dark shadow so it reads on any backdrop. Compute it in the browser at about 480 px, then scale it up:
  1. If the reference has real transparency (a cutout PNG), use alpha ≥ 128 as the mask.
  2. Otherwise, estimate the backdrop colour as the median of the border pixels, threshold each pixel's colour distance from it (Otsu, minimum 28), keep the largest connected blob and fill its holes.
  3. If that mask covers under 1 % or over 85 % of the image, fall back to Sobel edges (top 10 %).
  4. Draw the mask boundary, thickened by one pixel. Show a small badge saying which method was used.
- **Grid toggle:** thirds plus a centre cross. Draw each line twice, a dark under-stroke and then a light stroke, so it's visible on white and on black.

**Capture: the overlay must never be in the photo**

- Save the photo with `ImageCapture.takePhoto()` (full sensor resolution). Fall back to drawing the video element, never the overlay, onto a canvas and saving it as JPEG at 0.95.
- **At the same moment, grab the current video frame (about 1280 px) and use that as the next reference**, not the takePhoto result. takePhoto's field of view can differ from the stream's, so a reference made from it won't line up with the live view.
- By default each new photo becomes the next reference ("follow last photo"). Let the user turn that off to keep one master reference, use the last photo, load any image from the phone (a transparent PNG gives the cleanest outline), or remove the reference.

**Camera settings that keep a set consistent** (show each control only where `getCapabilities()` supports it)

- **Lock:** read `getSettings()` and apply manual mode with the current `focusDistance`, `exposureTime` and `colorTemperature`, each in its own try/catch. Toast which of them actually locked. Unlock returns them to `continuous`.
- **Zoom slider**, with the value remembered.

**Photos**

- A **Set** name field at the top. Files are named `<set>-001.jpg`, `<set>-002.jpg` …
- Keep the photos and the current reference in **IndexedDB** so they survive a reload. Keep settings (mode, opacity, grid, zoom, set name, follow-last) in localStorage, with every access wrapped in try/catch.
- A Photos sheet with thumbnails, per-photo delete, **Download all** (sequential `<a download>` clicks), **Share all** (`navigator.share` with files, only shown if `canShare` exists), and **Delete all** with an in-page confirmation. Never use `confirm()`.

**Sending to the PC**

- On load, `GET api/status`. If it answers, the app is being served by the PC: show a status chip in the top bar.
- After each capture, `POST api/upload` with the image as the body and the headers `Content-Type`, `X-Object-Name` (the set name) and `X-Taken` (capture time in ms). Mark each photo sent or not sent and save that flag in IndexedDB.
- On failure, keep the photo, show **PC offline**, and offer **Send N photos to PC** in the Photos sheet.
- Keep the chip text short (**PC ready**, **PC starting**, **PC 3 left**, **PC 5 ✓**, **PC offline**, **PC error**); tapping it shows the full message as a toast. Poll status every 2 s only while the PC has work queued or is still starting.

**Layout pitfall:** the top bar must never be wider than the phone. Give the app grid `grid-template-columns: minmax(0, 1fr)`, let the Set field and PC chip shrink with ellipsis, give the dot and icons `flex: none`, and under 440 px hide the Grid button's text and the "Set" label. Check at 360 px and 412 px widths that `document.documentElement.scrollWidth` equals the viewport width and the Photos button is fully on screen.

## PC side: `serve.py`

- **Certificate:** find the PC's LAN IP (UDP-connect trick, no packets sent). Generate a self-signed certificate valid for that IP, `127.0.0.1` and `localhost`. Use the `cryptography` package (EC P-256, 825 days), falling back to the `openssl` command. Store it in `.cert/` and regenerate only if the IP changes. Add `.cert/` and `photos/` to `.gitignore`.
- **Serve only an allowlist** of the app's own files: `/`, `/index.html`, the manifest, the icon and `sw.js`, with `Cache-Control: no-cache`. **Do not use `SimpleHTTPRequestHandler` on the folder**: that would hand the private key in `.cert/` and the photos to anyone on the Wi-Fi. Everything else returns 404, including `..` paths.
- `GET /api/status` returns `{ok, queued, done, failed, last, ready, error}`.
- `POST /api/upload`: reject bodies over 60 MB, save the original to `photos/originals/<object>_<timestamp>.<ext>`, queue it, and answer immediately.
- **One background worker thread** loads the model at startup (so the first photo isn't slow), then processes the queue one photo at a time, printing `finished <name>` or `FAILED <name>: <reason>`. If the model fails to load, report it through `error` with the fix (`pip install -r requirements.txt`).
- Command-line options: `--port` (default 8443) and `--out` (default `./photos`).
- On start, print the `https://<LAN-IP>:8443` address to open on the phone, the Chrome "Advanced → Proceed" step, and the output folders.

## The finishing step: `process.py`

- Use **rembg** with the **`birefnet-general`** model, which is the most robust free option. Before cutting, apply `ImageOps.exif_transpose` so phone rotation is respected.
- **Memory, important:** create the onnxruntime session with `enable_cpu_mem_arena = False` and `enable_mem_pattern = False`, passed in as `rembg.new_session(model, sess_opts=opts)`. Without this, one photo takes over 9 GB and memory grows with every photo until the process is killed. With it, the peak is about 8 GB during a cutout and it settles around 2 GB between photos. Limiting threads or graph optimisation does not reduce the peak.
- **Low-RAM PCs:** detect total RAM (Windows `GlobalMemoryStatusEx` through ctypes, macOS `sysctl hw.memsize`, Linux `/proc/meminfo`). Under 12 GB, use `isnet-general-use` instead (under 1 GB, about 1 s per photo) and print a one-line note at startup. `birefnet-general-lite` is not worth it: it still peaks around 6.8 GB.
- **Download the model yourself**, with a progress display, into `~/.u2net/<rembg-model-name>.onnx`. rembg's own downloader times out after 30 s on slow connections. The release files are at `https://github.com/danielgatis/rembg/releases/download/v0.0.0/`, and the BiRefNet file names differ from rembg's model names:
  - `birefnet-general` → `BiRefNet-general-epoch_244.onnx` (about 900 MB)
  - `isnet-general-use` → `isnet-general-use.onnx` (about 170 MB)
- **Finishing:** cut out with `post_process_mask=True`. Feather the alpha: erode by `round(f/2)` px, Gaussian blur at radius `f/2`, then multiply by the original alpha. This keeps the softening inside the edge, so there's no halo of old background. Crop to the alpha bounding box (alpha > 8), scale with LANCZOS to fit 900 × 900, centre on white 1000 × 1000, and save as JPEG at quality 95 with `subsampling=0`.
- **Date:** EXIF `DateTimeOriginal`, then `DateTime`, then the upload's capture time, then today.
- **Name:** lowercase the object name and replace anything other than letters, digits, `_` and `-` with `-`. Fall back to `product`. Never overwrite an existing file; add `_2`, `_3` instead.
- Put `SIZE = 1000`, `MARGIN = 50` and `FEATHER = 2.0` as constants at the top so they're easy to change.
- Also work as a standalone tool: `python process.py <file-or-folder> --name blue-mug [--out finished]`.

## Check your work before handing over

Test with headless Chromium (Playwright) using a fake camera: `--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream` and `--use-file-for-fake-video-capture=product.y4m`. Generate the `.y4m` from a test image of a simple product on a plain light backdrop. Use `ignoreHTTPSErrors` against `https://localhost:8443`. Confirm all of the following:

1. The camera starts, a photo is taken, and the reference and outline are drawn.
2. **A photo taken while the outline is showing contains no outline-coloured pixels.**
3. Photos and the reference survive a page reload.
4. With the server running, the two photos taken with Set "Blue Mug" produce `blue-mug_<today>.jpg` and `blue-mug_<today>_2.jpg` in `photos/finished/`. Each is 1000 × 1000 with white corners, and the item's bounding box touches the 50 px margin on its longer side and is centred on the other.
5. `GET /.cert/key.pem`, `/serve.py` and `/photos/` all return 404.
6. Process three photos in a row in one process and confirm memory returns to about 2 GB between photos rather than growing.
7. The top bar fits at 360 px and 412 px widths.

Then give the user short, plain steps:

- `pip install -r requirements.txt`, then `python serve.py`.
- The first start downloads about 900 MB.
- Open the printed address in Chrome on the phone, on the same Wi-Fi, and tap **Advanced → Proceed**.
- On Windows, allow Python through the firewall for **Private networks**.
- Each photo takes 20 to 30 seconds on the PC.

## Decisions already made (don't revisit)

- Local only: no Bria or other API-based background removal, no accounts.
- A web app rather than a native Android app, served by the PC over HTTPS with a self-signed certificate rather than GitHub Pages.
- The object name comes from the Set name typed in the app, not from AI recognition.
- Keep the app simple: one default cutout model, chosen automatically by RAM, with no model picker shown to the user.
