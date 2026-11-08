#!/usr/bin/env python3
"""cuts.py - a cut list from a timestamped transcript. Prints decisions, never touches media.

    python3 cuts.py take.srt                # .srt, .vtt or Whisper .json
    python3 cuts.py take.srt --gap 0.35     # pause threshold in seconds (default 0.5)
    python3 cuts.py take.srt --json

Kinds:
  DEAD    pause longer than --gap; the middle is cut, a breath stays on each side
  FILLER  a cue that is only filler words
  RETAKE  an earlier attempt at a line that the next spoken line restarts
"""
import argparse
import json
import re
import sys

FILLER = {"um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "so", "okay", "ok", "right",
          "yeah", "like", "anyway", "basically", "actually", "well", "you know", "i mean",
          "sort of", "kind of"}
TIME = re.compile(r"(\d[\d:.,]*)\s*-->\s*(\d[\d:.,]*)")


def seconds(ts):
    parts = ts.strip().replace(",", ".").split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def clock(s):
    m, s = divmod(max(s, 0.0), 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:06.3f}" if h else f"{m}:{s:06.3f}"


def load(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if path.lower().endswith(".json"):
        data = json.loads(raw)
        segs = data.get("segments", []) if isinstance(data, dict) else data
        return [(float(s["start"]), float(s["end"]), (s.get("text") or "").strip())
                for s in segs if (s.get("text") or "").strip()]
    cues, cur = [], None
    for line in raw.splitlines():
        m = TIME.search(line)
        if m:
            cur = [seconds(m.group(1)), seconds(m.group(2)), []]
            cues.append(cur)
        elif cur is not None and line.strip() and not line.strip().isdigit():
            cur[2].append(re.sub(r"<[^>]+>", "", line.strip()))
    return [(a, b, " ".join(t)) for a, b, t in cues if t]


def words(text):
    return re.findall(r"[a-z']+", text.lower())


def is_filler(text):
    rest = " ".join(words(text))
    if not rest:
        return False
    for f in sorted(FILLER, key=len, reverse=True):
        rest = re.sub(rf"\b{re.escape(f)}\b", " ", rest)
    return not rest.strip()


def restarts(earlier, later, n=3):
    """True when `later` opens with the same first n words as `earlier`."""
    a, b = words(earlier), words(later)
    k = min(n, len(a), len(b))
    return k >= 2 and a[:k] == b[:k]


def find_cuts(cues, gap):
    cuts = []
    last_speech = None  # index of the last cue that was not filler
    for i, (start, end, text) in enumerate(cues):
        if i:
            pause = start - cues[i - 1][1]
            if pause > gap:
                keep = gap / 2
                cuts.append({"kind": "DEAD", "start": cues[i - 1][1] + keep, "end": start - keep,
                             "text": f"{pause:.2f}s pause"})
        if is_filler(text):
            cuts.append({"kind": "FILLER", "start": start, "end": end, "text": text})
            continue
        if last_speech is not None and restarts(cues[last_speech][2], text):
            s, e, t = cues[last_speech]
            cuts.append({"kind": "RETAKE", "start": s, "end": e, "text": t})
        last_speech = i
    return merge(cuts)


def merge(cuts):
    cuts = sorted((c for c in cuts if c["end"] > c["start"]), key=lambda c: c["start"])
    out = []
    for c in cuts:
        if out and c["start"] <= out[-1]["end"]:
            prev = out[-1]
            prev["end"] = max(prev["end"], c["end"])
            if c["kind"] not in prev["kind"].split("+"):
                prev["kind"] += "+" + c["kind"]
                prev["text"] += " | " + c["text"]
        else:
            out.append(dict(c))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript")
    ap.add_argument("--gap", type=float, default=0.5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cues = load(args.transcript)
    if not cues:
        sys.exit("no cues found: expected .srt, .vtt or Whisper .json")
    cuts = find_cuts(cues, args.gap)
    runtime = cues[-1][1]
    removed = sum(c["end"] - c["start"] for c in cuts)

    if args.json:
        json.dump({"runtime": round(runtime, 3), "removed": round(removed, 3), "after": round(runtime - removed, 3),
                   "cuts": [{**c, "start": round(c["start"], 3), "end": round(c["end"], 3)} for c in cuts]},
                  sys.stdout, indent=2)
        print()
        return

    print("| # | Kind | In | Out | Length | What |")
    print("|---|---|---|---|---|---|")
    for n, c in enumerate(cuts, 1):
        text = c["text"].replace("|", "/")[:70]
        print(f"| {n} | {c['kind']} | {clock(c['start'])} | {clock(c['end'])} | "
              f"{c['end'] - c['start']:.2f}s | {text} |")
    print()
    print(f"Runtime {clock(runtime)} -> {clock(runtime - removed)} "
          f"(cuts {removed:.1f}s, {100 * removed / runtime:.0f}% of the take)")


if __name__ == "__main__":
    main()
