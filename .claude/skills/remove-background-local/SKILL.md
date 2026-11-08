---
name: remove-background-local
description: Remove backgrounds from images locally and for free — transparent PNG cutouts, product cutouts, headshot/portrait cutouts, masks, white-background packshots, batch folders. Runs the open-source rembg models on this machine, so it needs no account, no API key, and no upload. Use this whenever the task is removing a background, making a background transparent, making a cutout, isolating or extracting the subject, or making a foreground mask. Prefer it over any API-based background removal skill unless the user specifically asks for Bria.
---

# Remove Background (local, no account)

Removes image backgrounds on this machine with [rembg](https://github.com/danielgatis/rembg) (MIT). No sign-up, no API key, and images never leave the machine.

## How to run

One script does everything. Run it from the repo root:

```bash
.claude/skills/remove-background-local/scripts/remove_bg.sh <input> [output] [options]
```

- `<input>` is an image file (jpg, png, webp, bmp, tif) or a folder of images.
- `[output]` is optional. A single file defaults to `<name>_cutout.png` next to the input. A folder defaults to `<folder>/cutouts/<name>.png`.
- The script prints each output path it writes.

The first run in a fresh environment takes 1–2 minutes: it creates a Python env in `~/.cache/remove-bg-local` and downloads the model (~170 MB) to `~/.u2net`. After that, each image takes a couple of seconds on CPU. Tell the user about the one-time wait before the first run.

## Options

| Option | What it does |
|---|---|
| `--feather [PX]` | Smooth jagged, stair-stepped edges. Bare `--feather` is a light 2 px; `--feather 4` is softer. Put it after the input path. |
| `--crop` | Crop to the subject. Add `--padding N` for N pixels of space around it. |
| `--bg ffffff` | Fill the background with a hex color instead of leaving it transparent (white packshot, brand color). |
| `--mask` | Output the black-and-white mask instead of the cutout. |
| `--alpha-matting` | Softer, cleaner edges on hair and fur. Slower. |
| `--model NAME` | Choose the model (see below). |

Save as `.png` to keep transparency. Saving to `.jpg` flattens the image, so pair it with `--bg`.

## Choosing a model

| Model | Use for |
|---|---|
| `isnet-general-use` (default) | Most photos: products, objects, people, animals |
| `u2net_human_seg` | People only. Try this if a portrait cutout keeps bits of background |
| `birefnet-portrait` | Highest-quality portraits and hair. ~900 MB download, slow on CPU |
| `birefnet-general` | Highest-quality general cutouts. ~900 MB download, slow on CPU |
| `isnet-anime` | Anime and illustrated characters |
| `u2net` | Older general model. Fallback if the default struggles |

Start with the default. Only reach for a BiRefNet model if the user isn't happy with the edges, and warn them about the download size.

## Examples

```bash
S=.claude/skills/remove-background-local/scripts/remove_bg.sh

$S photo.jpg                                   # -> photo_cutout.png (transparent)
$S product.jpg product_white.jpg --bg ffffff --crop --padding 40   # white packshot
$S headshot.jpg --model u2net_human_seg --alpha-matting           # portrait with fine hair
$S ./photos                                    # whole folder -> ./photos/cutouts/
$S photo.jpg --mask                            # -> photo_mask.png
$S photo.jpg --feather                         # smooth jagged edges (light)
```

## After running

- Look at the result before reporting back (open the PNG with the Read tool). Check that the whole subject was kept and the background is gone.
- If the edge looks jagged or stair-stepped, rerun with `--feather` (or `--feather 3`–`4` for softer). Keep it light on product shots, where crisp edges matter.
- If parts of the subject went missing or background remains, try another model (`u2net_human_seg` for people, `u2net`, or a `birefnet-*` model) and compare. When the subject's color blends into a busy background (an animal against a fence or foliage, say), the default often clips pieces such as an ear; `birefnet-general` handles that best (about 1 minute per image on CPU).
- Hand the user the output path(s).

## Limits

- It keeps the obvious main subject. It can't follow instructions like "keep the dog but drop the person". For that, crop the image first or edit the mask.
- Glass, smoke and very fine detail can come out rough. `--alpha-matting` or a BiRefNet model helps.
- The first run needs internet access to PyPI and GitHub to install the package and download the model. After that it works offline.
