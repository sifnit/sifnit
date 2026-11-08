---
name: edit
description: Plan and tighten the cut. Use for an edit plan, shot list, B-roll list, card list, "cut the dead air", "tighten this take", or turning script.md or a transcript into something an editor works from. Writing the words is script. Thumbnail is thumb.
---

# edit

Two jobs. Before the shoot, the script becomes a plan. After the shoot, the transcript becomes a cut list. Neither one touches media. You print the decisions. The editor applies them.

Load `profile` for palette, aspect and paths. Card text and receipts come from `script.md`. Do not write new claims here.

## 1. Plan (before recording)

Input: the video folder's `script.md`. If it is missing a slot, send it back to `script`.

Write `edit/plan.md` from `TEMPLATE.md` next to this file. One row per beat, in script order.

- **At**: running time at 150 spoken words per minute. Count the words. Do not guess.
- **Line**: the first words of the spoken line, enough to find it in the take.
- **Picture**: `A` (talking head), `B` (B-roll, say what), `CARD` (text on screen), `SCREEN` (capture, say the URL or app).
- **Card**: exact on-screen text. A number on a card has its source in the Sources column.
- **Change**: what resets attention here. Cut, angle, card, B-roll, sound. Something changes at least every 30 seconds in long form, every 3 seconds in Shorts. If a row has nothing, mark it `RISK` and say the fix.

Then two lists under the table: **Pickups** (B-roll and screens to shoot or capture) and **Cards** (every card, in order, with source). The editor works from those two lists.

Short (35–55s): every row is a beat of the script, every row has a change. Explainer cut: every receipt is a `CARD`.

## 2. Cut list (after recording)

Needs a timestamped transcript: SRT, VTT, or Whisper JSON. No transcript? Make one (`whisper take.mp4 --output_format srt`) or ask. Do not guess timings.

```bash
python3 cuts.py take.srt                 # table: DEAD, FILLER, RETAKE with timecodes
python3 cuts.py take.srt --gap 0.35      # cut pauses longer than 0.35s (default 0.5)
python3 cuts.py take.srt --json > edit/cuts.json
```

- **DEAD**: a pause longer than `--gap`. The script keeps a breath on each side and cuts the middle. Flush cuts sound gasping.
- **FILLER**: a cue that is only "um", "so", "basically" and friends.
- **RETAKE**: a line that restarts the line before it. The earlier attempt is marked for cutting, the last attempt stays. Check each one. The script keeps the last take, not the best one.

Write the result to `edit/cuts.md`: the table, the runtime before and after, and every RETAKE quoted so the human can overrule it.

The runtime math counts speech only. A silent screen demo looks like dead air. Read the list against the footage before trusting the total.

If `auto-editor` is installed and the user wants a rough file, `auto-editor take.mp4 --margin 0.2s` makes one. Say it is rough. The cut list is still the record.

## Fail

A plan row with no picture. A card number with no source. A cut list built from timings you estimated. A RETAKE cut you did not quote back.
