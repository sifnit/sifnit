# AD5X stock firmware test

Finds out what a stock (no ZMOD) AD5X will do when an app sends it
commands. Uses no filament, prints nothing, takes about 5-8 minutes.

## How to run
1. Clear the bed. No filament needs to be loaded.
2. Copy `stock-test.gcode` to a USB stick (or send it from Orca-Flashforge).
3. Start it like a normal print and **film the whole run**.
4. Fill in the table below.

The nozzle parks at a checkpoint along the front edge before each test
(checkpoint 1 is near the left, checkpoint 8 near the right). If the
print stops, the last checkpoint tells you which test stopped it.

If the printer refuses the file, slice a tiny cube in Orca-Flashforge,
paste the test lines into the printer's start G-code, and print that
(cancel once checkpoint 8 is reached).

## Results
| # | Test | What to look for | Result |
|---|---|---|---|
| — | Before checkpoint 1 | Did the printer do its own bed scan before the file started? | |
| 1 | Homing | Homes, then parks front-left | |
| 2 | Heating | Time from start of heating to moving on (bed 60 / nozzle 150) | |
| 3 | Fan | Part fan spins for 5 s | |
| 4 | Screen message | Does "AD5X TEST STEP 4" show on the screen? | |
| 5 | Small-area bed scan | Middle 3x3 only / whole bed / nothing | |
| 6 | Probe consistency | Taps the middle 5 times? | |
| 7 | Newer commands | Scans bed / skips / print stops with error (note the message) | |
| 8 | Finished | Reached the far-right park and cooled down | |

Firmware version (Settings → About): ______

## What the results mean
- **5 = middle only** → faster bed leveling works on stock.
- **6 = 5 taps** → probe consistency check works on stock.
- **7 stops with error** → stock Klipper is older; the app must stick to step 5 style commands.
- **Own bed scan before checkpoint 1** → stock always scans the full bed, so faster leveling
  needs ZMOD regardless of step 5.
- Stock can't report numbers back to an app, so even a pass here means
  "it runs", not "we can read the result". Reading results needs ZMOD.
