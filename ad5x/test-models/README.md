# Test models

| File | What it tests | Expected in the app |
|---|---|---|
| `beigelad-coin.stl` | Basic print. 40 mm coin, 3 mm thick, BEIGELAD raised 0.8 mm | ✓ Ready to print, no fixes |
| `standing-b.stl` | Letter B, 41 mm tall, standing up | "Better way up found" → Rotate lays it flat, supports no longer needed |

## Support test (do later)
Print `standing-b.stl` standing up, with supports, once per setting below.
Note how easily supports come off and how the underside looks (1-5).

| Filament | Goal | Supports | Top gap | Interface layers | Comes off | Underside |
|---|---|---|---|---|---|---|
| PLA | Everyday | Tree | 0.20 | 2 | | |
| PLA | Pretty | Tree | 0.15 | 3 | | |
| PLA | Fast | Tree | 0.25 | 1 | | |
| PETG | Everyday | Tree | 0.28 | 3 | | |
