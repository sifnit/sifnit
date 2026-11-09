# What does a stock AD5X let an app do?

Long format, about 9 to 11 minutes. Results from the test are not in yet:
every `[RESULT: ...]` is a placeholder to fill after filming.

## Hook A (family: Lived scene)
"You sliced it. You sent it. The printer was not on the Wi-Fi anymore."

## Hook B (family: Receipt)
"I sent my AD5X eight commands it was never meant to get. [RESULT: N] of them worked."

## Hook C (family: Status)
"If you need to know what a Z offset is to get a good print, the slicer failed. Not you."

## Chosen hook
Hook B. It is a number, it is on camera, and it sets up the whole video.
Cold open: 1 second of the nozzle parking at checkpoint 1, then the line.

## Promise
By the end you will know what a stock AD5X will take from an app without any mods,
what needs ZMOD, and whether my one-tap slicer can work on yours as it ships.

## Beats

### Beat 1: Why I am doing this
- Claim: Slicers make beginners learn printing settings before they can print.
- Receipt: Screen recording. OrcaSlicer settings panel, scrolled top to bottom, real time.
  Tom's Hardware's AD5X review also flagged the bundled Flashforge slicer crashing.
- Line: "This is every setting in the slicer most AD5X owners use. I scrolled at normal speed.
  It took [RESULT: seconds]. I want a slicer where you pick what you are making
  and it handles the rest. Fast. Strong. Pretty. Then one button to print."
- Visual / card: Settings panel scroll, timer in the corner. Card: "Tom's Hardware: Flashforge's slicer crashed often."
- Turn: Before building an easy slicer, I need to know what the printer will listen to.

### Beat 2: The problem with stock firmware
- Claim: The AD5X runs Klipper underneath, but stock firmware keeps it locked.
- Receipt: ZMOD wiki and SimplyPrint setup guide. With ZMOD you get the Fluidd web
  dashboard and an API on port 7125. Stock gives you neither.
- Line: "Inside, this printer runs Klipper. Same software as printers that cost three times
  as much. But Flashforge locks it. No dashboard. No way for my app to ask the printer
  how level the bed is. The community fix is ZMOD. It installs from a USB stick.
  It can take up to 40 minutes. Most people buying this printer will never install it.
  So the question is: what can I do without it?"
- Visual / card: Split screen. Left: stock touchscreen. Right: Fluidd dashboard on a ZMOD printer.
  Card: "ZMOD: stock firmware 1.0.2 to 1.1.7. Install up to 40 min."
- Turn: An app can still send the printer a job file. So I wrote a job that is a test.

### Beat 3: The test file
- Claim: One file, eight tests, no filament, nothing printed.
- Receipt: The file on screen. `stock-test.gcode`.
- Line: "Before each test, the nozzle parks at a numbered spot along the front.
  One on the left, eight on the right. If it stops, I know exactly which test killed it.
  Homing. Heating. Fan. A message on the screen. A small bed scan. A probe test.
  Newer Klipper commands. Then cool down."
- Visual / card: Top-down shot of the bed with checkpoints 1 to 8 marked in tape.
  Overlay the list as the nozzle moves.
- Turn: First, the boring ones.

### Beat 4: The basics (checkpoints 1 to 4)
- Claim: Homing, heating and fans are the floor. If these fail, nothing else matters.
- Receipt: On-camera run.
- Line: "Homing: [RESULT]. Heating to 60 on the bed and 150 on the nozzle took
  [RESULT: time]. Fan: [RESULT]. Then I asked it to put a message on its own screen.
  [RESULT: shown / ignored]."
- Visual / card: Timer overlay for heating. Close-up of the screen at checkpoint 4.
- Turn: [If the message showed: "So the app can talk to you through the printer's screen."
  If not: "So the app cannot use the printer's screen. Noted."]

### Beat 5: The test that matters (checkpoint 5)
- Claim: Scanning only the area you print on makes every print start faster.
- Receipt: On-camera run. Does it probe a 3 by 3 grid in the middle, the whole bed, or nothing?
  Also: did the printer run its own full scan before the file started?
- Line: "Normally the printer scans the whole bed before every print, even for a keychain.
  I asked it to scan only the middle. It [RESULT: scanned the middle / scanned everything /
  did nothing]."
- Visual / card: Top-down, time-lapse, probe points marked as they happen.
  Card: "Middle only = faster starts on stock."
- Turn: [Pass: "That alone saves [RESULT: time] on every small print, no mods."
  Fail: "So on stock, faster starts need ZMOD."]

### Beat 6: Probe test and newer commands (checkpoints 6 and 7)
- Claim: These decide whether a one-tap health check can run on stock.
- Receipt: On-camera. Five taps in the middle, or not. Then checkpoint 7: [RESULT: ran / skipped / error message].
- Line: "Five taps on the same spot tells you if the probe is consistent. It [RESULT].
  Checkpoint seven uses commands from newer Klipper. [RESULT]. Here is the catch.
  Even when a test runs, stock cannot send the numbers back to my app.
  It can do the check. It cannot tell me the answer."
- Visual / card: Close-up of the nozzle tapping. Card with the error text if checkpoint 7 failed.
- Turn: That is the real line between stock and ZMOD.

### Beat 7: The Wi-Fi problem
- Claim: My AD5X drops off the Wi-Fi within a day.
- Receipt: My own log. Times it was offline over [RESULT: days].
- Line: "Mine falls off the network within 24 hours. A one-tap app is useless if
  the printer is not there. Two fixes. First, the router. Its own 2.4 gigahertz network,
  a fixed address, band steering off. Free, no mods. If that does not hold,
  a small script that turns off Wi-Fi power saving and reconnects when it drops.
  That one needs ZMOD. Reboot and it is gone."
- Visual / card: Router settings screen. Then the script log showing a reconnect.
  Card: "Router fix first. Script needs ZMOD."
- Turn: [RESULT: did the router fix alone hold for 48 hours?]

## Payoff
"[RESULT: N] of 8 work on stock. So the one-tap slicer works on a stock AD5X for
[RESULT: list]. For [RESULT: list], you need ZMOD, and the app will tell you
when, instead of making you guess."

## Outro
"Next video I build the first version. Drop a model, pick what you are making,
one button to print. On this exact printer. The test file and the Wi-Fi fix are
free and linked below."
Not-advice card (installing mods): "Installing ZMOD is at your own risk. Check the ZMOD wiki first."

## Sources
- ZMOD project (ghzserg). GitHub. https://github.com/ghzserg/zmod
- ZMOD wiki. https://wiki.zmod.link
- SimplyPrint (2025). Setting up SimplyPrint on Flashforge AD5X (firmware 1.0.2 to 1.1.7, install up to 40 min, Moonraker port 7125). https://simplyprint.io/setup-guide/flashforge/ad5x/on-printer
- Tom's Hardware. Flashforge AD5X review. https://www.tomshardware.com/3d-printing/flashforge-ad5x-review
- Flashforge. Orca-Flashforge. https://www.flashforge.com/pages/orca-flashforge
- Own footage: stock-test.gcode run, Wi-Fi log. Files in this repo, `ad5x/`.

## Thumb line
"[N]/8 WORKED ON STOCK"

## Description
I sent a stock Flashforge AD5X eight commands it was never meant to get. [N] worked.
Here is what an app can do on stock, what needs ZMOD, and the fix for the AD5X dropping off Wi-Fi.

Test file and Wi-Fi fix: [LINK]

Sources:
ZMOD: https://github.com/ghzserg/zmod
ZMOD wiki: https://wiki.zmod.link
SimplyPrint AD5X guide: https://simplyprint.io/setup-guide/flashforge/ad5x/on-printer
Tom's Hardware AD5X review: https://www.tomshardware.com/3d-printing/flashforge-ad5x-review

## Titles
1. I Sent My AD5X 8 Commands It Wasn't Meant to Get
2. What a Stock AD5X Lets an App Do (No Mods)
3. Do You Actually Need ZMOD on the AD5X?
4. My AD5X Kept Dropping Off Wi-Fi. Here's the Fix.
5. Building a One-Tap Slicer for the AD5X: Test 1
