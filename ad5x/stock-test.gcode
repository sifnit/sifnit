; AD5X stock firmware test - no filament used, nothing gets printed.
; Before each test the nozzle parks at a CHECKPOINT along the front edge
; and waits 5 s. Checkpoint N = X at N x 20 mm from the left.
; Film the whole run. Fill in STOCK-TEST.md afterwards.
; Remove any print from the bed before starting.

G90 ; absolute positioning
M82

; ---------- CHECKPOINT 1: homing ----------
G28
G1 Z10 F600
G1 X20 Y10 F6000
G4 P5000

; ---------- CHECKPOINT 2: heating (time it) ----------
G1 X40 Y10 F6000
G4 P5000
M140 S60  ; bed 60C
M104 S150 ; nozzle 150C (low, so it won't ooze)
M190 S60
M109 S150

; ---------- CHECKPOINT 3: part cooling fan ----------
G1 X60 Y10 F6000
G4 P5000
M106 S255
G4 P5000
M107

; ---------- CHECKPOINT 4: screen message ----------
G1 X80 Y10 F6000
G4 P5000
M117 AD5X TEST STEP 4
G4 P10000 ; look at the screen now

; ---------- CHECKPOINT 5: small-area bed scan ----------
; PASS = probes only a 3x3 grid in the middle of the bed.
; Whole bed probed = stock ignores the area. Nothing = command ignored.
G1 X100 Y10 F6000
G4 P5000
BED_MESH_CLEAR
BED_MESH_CALIBRATE MESH_MIN=90,90 MESH_MAX=130,130 PROBE_COUNT=3,3

; ---------- CHECKPOINT 6: probe consistency ----------
; PASS = taps the middle of the bed 5 times.
G1 Z10 F600
G1 X120 Y10 F6000
G4 P5000
G1 X110 Y110 F6000
PROBE_ACCURACY SAMPLES=5

; ---------- CHECKPOINT 7: newer Klipper commands ----------
; If the print stops with an error here, stock Klipper is too old for these.
G1 Z10 F600
G1 X140 Y10 F6000
G4 P5000
EXCLUDE_OBJECT_DEFINE NAME=test_box CENTER=110,110 POLYGON=[[100,100],[120,100],[120,120],[100,120]]
BED_MESH_CLEAR
BED_MESH_CALIBRATE ADAPTIVE=1

; ---------- CHECKPOINT 8: finished ----------
G1 Z10 F600
G1 X160 Y10 F6000
G4 P5000
M104 S0
M140 S0
M107
M84
