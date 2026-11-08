#!/usr/bin/env python3
"""Turn product photos into finished listing images:
cut out the item, light feather, centre it on a white 1000x1000 square with a small border,
and name the file <object>_<date>.jpg.

serve.py runs this automatically for every photo the phone sends. You can also run it on
photos already on the PC:

    python process.py photo.jpg --name blue-mug
    python process.py some-folder --name blue-mug      # every image in the folder
"""
import argparse
import os
import re
import sys
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

SIZE = 1000         # output is SIZE x SIZE
MARGIN = 50         # white border on each side, so the item fits in 900 x 900
FEATHER = 2.0       # light edge softening, in pixels
# Best cutouts need about 8 GB of RAM while working; PCs with less get a lighter model (under 1 GB).
MODELS = {
    "birefnet-general": ("BiRefNet-general-epoch_244.onnx", "about 900 MB"),
    "isnet-general-use": ("isnet-general-use.onnx", "about 170 MB"),
}
RELEASES = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

_session = None
_lock = threading.Lock()


def total_ram_gb():
    try:
        if sys.platform == "win32":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 2**30
        if sys.platform == "darwin":
            import subprocess
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 2**30
        with open("/proc/meminfo") as f:
            return int(f.readline().split()[1]) / 2**20
    except Exception:
        return None


def pick_model():
    forced = os.environ.get("PRODUCT_CAMERA_MODEL")
    if forced in MODELS:
        return forced
    ram = total_ram_gb()
    return "birefnet-general" if ram is None or ram >= 12 else "isnet-general-use"


MODEL = pick_model()


def model_dir():
    return Path(os.environ.get("U2NET_HOME", Path.home() / ".u2net"))


def ensure_model():
    """Download the cutout model once, with progress. rembg's own downloader gives up on slow links."""
    path = model_dir() / f"{MODEL}.onnx"
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    remote, size = MODELS[MODEL]
    print(f"Downloading the cutout model ({size}, one time only)...", flush=True)
    with urllib.request.urlopen(RELEASES + remote) as r, open(part, "wb") as f:
        total, done, last = int(r.headers.get("Content-Length") or 0), 0, -1
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            pct = done * 100 // total if total else 0
            if pct != last and pct % 5 == 0:
                print(f"  {pct}%", flush=True)
                last = pct
    part.replace(path)
    print("Model ready.", flush=True)


def session():
    global _session
    with _lock:
        if _session is None:
            ensure_model()
            import onnxruntime as ort
            from rembg import new_session
            # Without these, the engine keeps every buffer it ever used: 9+ GB after one photo,
            # growing with each one. With them it frees memory between photos.
            opts = ort.SessionOptions()
            opts.enable_cpu_mem_arena = False
            opts.enable_mem_pattern = False
            _session = new_session(MODEL, sess_opts=opts)
    return _session


def feather(alpha, amount):
    """Soften the edge slightly inward so no background halo shows."""
    shrink = max(1, round(amount / 2))
    soft = alpha.filter(ImageFilter.MinFilter(2 * shrink + 1)).filter(ImageFilter.GaussianBlur(amount / 2))
    return ImageChops.multiply(soft, alpha)


def finish(img):
    """Photo in, finished 1000x1000 white-background image out."""
    from rembg import remove

    img = ImageOps.exif_transpose(img).convert("RGB")  # respect phone rotation
    cut = remove(img, session=session(), post_process_mask=True).convert("RGBA")
    alpha = feather(cut.getchannel("A"), FEATHER)
    cut.putalpha(alpha)

    box = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box:
        raise ValueError("couldn't find an item in the photo")
    item = cut.crop(box)

    room = SIZE - 2 * MARGIN
    scale = min(room / item.width, room / item.height)
    item = item.resize((max(1, round(item.width * scale)), max(1, round(item.height * scale))), Image.LANCZOS)

    canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
    canvas.alpha_composite(item, ((SIZE - item.width) // 2, (SIZE - item.height) // 2))
    return canvas.convert("RGB")


def clean_name(name):
    name = re.sub(r"[^\w-]+", "-", (name or "").strip().lower()).strip("-_")
    return name or "product"


def taken_date(img, fallback=None):
    """Date the photo was taken: from the photo's EXIF if it has one, else the fallback, else today."""
    try:
        exif = img.getexif()
        raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal, else DateTime
        if raw:
            return datetime.strptime(str(raw)[:10], "%Y:%m:%d").date()
    except Exception:
        pass
    return (fallback or datetime.now()).date()


def out_path(folder, name, day):
    """<name>_<YYYY-MM-DD>.jpg, then _2, _3 ... for more of the same object that day."""
    folder.mkdir(parents=True, exist_ok=True)
    base = f"{clean_name(name)}_{day.isoformat()}"
    p, n = folder / f"{base}.jpg", 2
    while p.exists():
        p, n = folder / f"{base}_{n}.jpg", n + 1
    return p


def process_file(src, out_dir, name, taken=None):
    with Image.open(src) as img:
        img.load()
        day = taken_date(img, taken)
        result = finish(img)
    dst = out_path(Path(out_dir), name, day)
    result.save(dst, "JPEG", quality=95, subsampling=0)
    return dst


def main():
    p = argparse.ArgumentParser(description="Make finished 1000x1000 white-background product images.")
    p.add_argument("input", help="photo or folder of photos")
    p.add_argument("--name", required=True, help="object name used in the file name, e.g. blue-mug")
    p.add_argument("--out", default="finished", help="output folder (default: ./finished)")
    args = p.parse_args()

    src = Path(args.input)
    files = sorted(f for f in src.iterdir() if f.suffix.lower() in EXTS) if src.is_dir() else [src]
    if not files or not files[0].exists():
        sys.exit(f"No photos found at {src}")
    failed = 0
    for f in files:
        try:
            print(process_file(f, args.out, args.name), flush=True)
        except Exception as e:
            failed += 1
            print(f"FAILED {f}: {e}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
