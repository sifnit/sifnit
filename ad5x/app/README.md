# AD5X Easy Slicer (UI prototype)

Open `index.html` in a browser (needs internet for three.js from jsDelivr).
Single file, so it can be wrapped with Pake or Tauri later.

## Works now
- Drop an STL (or use a sample), 3D view of the AD5X bed
- Pick a goal: Fast / Everyday / Strong / Pretty
- Pick one of 4 filament slots (demo data)
- Checks, each with a one-tap fix and Undo:
  too big, made in inches, better way up, parts hanging in the air (shown red),
  small base, holes in the mesh, TPU on Fast
- Rough time and filament estimate
- Print shows the settings and downloads them as JSON (OrcaSlicer setting names)

## Not yet
- Real slicing (OrcaSlicer engine)
- Sending to the printer, reading real slot contents
- 3MF / multi-color models
