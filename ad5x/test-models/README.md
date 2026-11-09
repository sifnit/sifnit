# Test models

| File | What it tests | Expected in the app |
|---|---|---|
| `beigelad-coin.stl` | Basic print. 40 mm coin, 3 mm thick, top 1 mm sticks out 1 mm (a lip), BEIGELAD raised 0.8 mm | ✓ Ready to print, "Small lips print fine" (122 mm²) |
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

## Speed test
Pick **Speed test** in the app: 0.32 mm layers, 2 walls, 5% infill, 600 mm/s,
20,000 mm/s² acceleration (AD5X advertised maximums, not yet verified), first layer
kept at 60 mm/s so it sticks. Print the coin and time it. Quality is not the point.
