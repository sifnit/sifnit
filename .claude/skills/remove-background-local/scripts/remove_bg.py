"""Remove image backgrounds locally with rembg. Run through remove_bg.sh, which sets up the env."""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter
from rembg import new_session, remove

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def parse_color(s):
    s = s.lstrip("#")
    if len(s) == 6:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    raise argparse.ArgumentTypeError("use a hex color like ffffff")


def feather(alpha, amount):
    """Soften a hard, jagged alpha edge. The soft edge is pulled slightly inward and
    clipped to the original mask, so no background halo shows outside the subject."""
    if amount <= 0:
        return alpha
    shrink = max(1, round(amount / 2))
    soft = alpha.filter(ImageFilter.MinFilter(2 * shrink + 1)).filter(ImageFilter.GaussianBlur(amount / 2))
    return ImageChops.multiply(soft, alpha)


def process(src, dst, session, args):
    img = Image.open(src)
    out = remove(
        img,
        session=session,
        only_mask=args.mask,
        alpha_matting=args.alpha_matting,
        post_process_mask=True,
    )
    if args.feather:
        if args.mask:
            out = feather(out.convert("L"), args.feather)
        else:
            out = out.convert("RGBA")
            out.putalpha(feather(out.getchannel("A"), args.feather))
    if args.crop and not args.mask:
        box = out.getbbox()
        if box:
            pad = args.padding
            box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
                   min(box[2] + pad, out.width), min(box[3] + pad, out.height))
            out = out.crop(box)
    if args.bg and not args.mask:
        canvas = Image.new("RGBA", out.size, args.bg)
        canvas.alpha_composite(out.convert("RGBA"))
        out = canvas
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.suffix.lower() in {".jpg", ".jpeg"}:
        out = out.convert("RGB")  # JPEG has no transparency
    out.save(dst)
    print(dst)


def main():
    p = argparse.ArgumentParser(description="Remove image backgrounds locally.")
    p.add_argument("input", help="image file or folder of images")
    p.add_argument("output", nargs="?", help="output file or folder (default: <name>_cutout.png next to input)")
    p.add_argument("--model", default="isnet-general-use",
                   help="isnet-general-use (default), u2net, u2net_human_seg, isnet-anime, birefnet-general, birefnet-portrait")
    p.add_argument("--mask", action="store_true", help="output the black/white mask instead of the cutout")
    p.add_argument("--alpha-matting", action="store_true", help="softer edges for hair/fur (slower)")
    p.add_argument("--feather", type=float, nargs="?", const=2.0, default=0.0, metavar="PX",
                   help="soften jagged edges; optional strength in pixels (default 2 if given without a number)")
    p.add_argument("--crop", action="store_true", help="crop to the subject")
    p.add_argument("--padding", type=int, default=0, help="pixels of padding around --crop")
    p.add_argument("--bg", type=parse_color, help="fill background with a hex color instead of transparency, e.g. ffffff")
    args = p.parse_args()

    src = Path(args.input).expanduser()
    session = new_session(args.model)

    if src.is_dir():
        out_dir = Path(args.output).expanduser() if args.output else src / "cutouts"
        files = sorted(f for f in src.iterdir() if f.suffix.lower() in EXTS)
        if not files:
            sys.exit(f"No images found in {src}")
        failed = 0
        for f in files:
            try:
                process(f, out_dir / f"{f.stem}.png", session, args)
            except Exception as e:  # keep going on bad files
                failed += 1
                print(f"FAILED {f}: {e}", file=sys.stderr)
        sys.exit(1 if failed else 0)

    if not src.is_file():
        sys.exit(f"Not found: {src}")
    dst = Path(args.output).expanduser() if args.output else src.with_name(f"{src.stem}_{'mask' if args.mask else 'cutout'}.png")
    process(src, dst, session, args)


if __name__ == "__main__":
    main()
