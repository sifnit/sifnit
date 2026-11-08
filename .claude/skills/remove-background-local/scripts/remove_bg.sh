#!/usr/bin/env bash
# Local background removal with rembg. No account, no API key; images never leave the machine.
# Usage: remove_bg.sh <input file or folder> [output file or folder] [options passed to remove_bg.py]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE="${REMOVE_BG_HOME:-$HOME/.cache/remove-bg-local}"
VENV="$CACHE/venv"
MODEL_DIR="${U2NET_HOME:-$HOME/.u2net}"
export U2NET_HOME="$MODEL_DIR"

# Pick the model from the args (default isnet-general-use) so it can be fetched up front.
MODEL="isnet-general-use"
prev=""
for a in "$@"; do
  [ "$prev" = "--model" ] && MODEL="$a"
  case "$a" in --model=*) MODEL="${a#--model=}" ;; esac
  prev="$a"
done

# 1. One-time setup: a private Python env with rembg (CPU).
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import rembg" 2>/dev/null; then
  echo "First run: installing rembg into $VENV (one time, ~1 min)..." >&2
  mkdir -p "$CACHE"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check "rembg[cpu]" >&2
fi

# 2. One-time per model: download weights with curl (rembg's own downloader times out on slow links).
if [ ! -s "$MODEL_DIR/$MODEL.onnx" ]; then
  echo "Downloading model $MODEL (one time)..." >&2
  mkdir -p "$MODEL_DIR"
  case "$MODEL" in  # BiRefNet weights are published under longer filenames
    birefnet-general)  REMOTE="BiRefNet-general-epoch_244" ;;
    birefnet-portrait) REMOTE="BiRefNet-portrait-epoch_150" ;;
    *)                 REMOTE="$MODEL" ;;
  esac
  curl -fsSL --retry 3 -o "$MODEL_DIR/$MODEL.onnx.part" \
    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/$REMOTE.onnx"
  mv "$MODEL_DIR/$MODEL.onnx.part" "$MODEL_DIR/$MODEL.onnx"
fi

exec "$VENV/bin/python" -I "$HERE/remove_bg.py" "$@"
