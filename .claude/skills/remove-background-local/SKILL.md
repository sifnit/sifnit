---
name: remove-background-local
description: Remove backgrounds from images locally and for free — transparent PNG cutouts, product cutouts, portraits, pets and animals, masks, white-background packshots, batch folders. Runs the open-source BiRefNet model on this machine, so it needs no account, no API key, and no upload. Use this whenever the task is removing a background, making a background transparent, making a cutout, isolating or extracting the subject, or making a foreground mask.
---

# Remove Background (local, free, no account)

Removes image backgrounds on this machine with BiRefNet through [rembg](https://github.com/danielgatis/rembg) (MIT). No sign-up, no API key, and images never leave the machine.

## How to run

From the repo root:

```bash
.claude/skills/remove-background-local/scripts/remove_bg.sh <input> [output] [options]
```

- `<input>` is an image file (jpg, png, webp, bmp, tif) or a folder of images.
- `[output]` is optional. A single file defaults to `<name>_cutout.png` next to the input. A folder defaults to `<folder>/cutouts/<name>.png`.
- Put options after the input path.

The first run in a fresh environment takes 2–3 minutes to install rembg and download the model (~900 MB). Tell the user about that wait first. After that, an image takes about 20–30 seconds on CPU.

## Options

| Option | What it does |
|---|---|
| `--touch-up` | Refines the edge to bring back fur, hair and thin parts (ears, tails, fingers) that the first pass clipped. |
| `--feather [PX]` | Smooths jagged, stair-stepped edges. Bare `--feather` is light (2 px). Don't combine with `--touch-up`. |
| `--crop` | Crops to the subject. Add `--padding N` for space around it. |
| `--bg ffffff` | Fills the background with a hex color instead of transparency. |
| `--mask` | Outputs the black-and-white mask instead of the cutout. |
| `--fast` | Uses a lighter model (~2 s per image) for big batches. Less accurate. |

Save as `.png` to keep transparency. A `.jpg` output needs `--bg`.

## Workflow

1. Run it with no options.
2. Look at the result before reporting back (open the PNG with the Read tool). Zoom in on thin parts and on edges where the subject matches the background.
3. If something was clipped, or a furry or hairy edge looks cut off, rerun with `--touch-up`. If the edge only looks jagged, rerun with `--feather`.
4. Give the user the output path. If they see a colored or checkered background, explain that it's their viewer showing the transparency.

## Examples

```bash
S=.claude/skills/remove-background-local/scripts/remove_bg.sh

$S photo.jpg                                    # -> photo_cutout.png
$S dog.jpg --touch-up                           # recover fur / ears
$S product.jpg product_white.jpg --bg ffffff --crop --padding 40
$S ./photos                                     # whole folder -> ./photos/cutouts/
$S ./photos --fast                              # big batch, quicker
```

## Limits

- It keeps the obvious main subject. It can't follow instructions like "keep the dog, drop the person", so crop first.
- Glass, smoke and see-through objects can come out rough.
- The first run needs internet access to PyPI and GitHub. After that it works offline.
