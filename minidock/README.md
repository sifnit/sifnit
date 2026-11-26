# MiniDock

A small taskbar replacement for Windows 10/11:

- Sits on **one monitor only**: whichever you choose.
- **Only as wide as its icons**, centered at the bottom with rounded corners, not the full width of the screen.
- **Grouped by app**, like the normal Windows 11 taskbar: one icon per app, no matter how many windows it has open.

## Install

1. Install **AutoHotkey v2** from https://www.autohotkey.com.
2. Put this `minidock` folder anywhere, e.g. `Documents\MiniDock`.
3. Double-click `MiniDock.ahk`.

The normal Windows taskbar is hidden while MiniDock runs and comes back when you exit.

## Using it

| Action | What happens |
|---|---|
| Click an app with 1 window | Switch to it (click again to minimize) |
| Click an app with several windows | A list of its windows pops up; pick one |
| Click a pinned app that isn't open | Opens it |
| Middle-click an icon | Opens a new window of that app |
| Right-click an icon | Window list, Open new window, Pin/Unpin, Close |
| Right-click empty dock space / tray icon | Choose monitor, Start with Windows, Exit |
| ⊞ button / Win key | Start menu |
| 🔊 button | Pick speaker/mic, volume, mute, auto-switch rules |
| Scroll over 🔊 | Volume up/down |
| Clock | Calendar and notifications |

Underline colors: **blue** means the app you're using now, **gray** means open, and **wider gray** means several windows are open. Pinned apps that aren't running have no line.

To choose the screen, right-click the tray icon (the green **H** near the clock area, or right-click empty space on the dock) and pick **Put dock on monitor N**. Your choice is remembered.

## Sound: keep the Bluetooth headset as default

Windows switches your default sound device whenever a new one appears, for example when you plug in a monitor that has speakers. MiniDock stops that:

- **Headset on:** speaker and mic go to the headset, even when you plug in screens.
- **Headset off:** they go to your **backup** device (e.g. PC speakers), never the monitor.
- **You switch manually** (from the 🔊 menu or Windows): your choice is left alone until something is plugged in or out again.

The first time it runs, it picks your Bluetooth headset as **preferred** and your current non-monitor device as **backup**. To change either, click 🔊, choose **Auto-switch**, then pick the preferred/backup speaker and microphone. The headset is listed even when it's off. Settings are saved in `MiniDock.ini`.

**Bluetooth tip:** many headsets show up twice, as "Headphones" (good stereo sound) and "Headset / Hands-Free" (includes the mic, but phone-call quality). If music sounds bad whenever the headset mic is the default, set **Preferred microphone** to your PC/webcam mic instead.

## Settings

Open `MiniDock.ahk` in Notepad and edit the `SETTINGS` block at the top. Then right-click the tray icon and choose **Reload**.

- `ICON_SIZE`: make it smaller (e.g. `20`) or bigger.
- `CELL_PADDING`, `ICON_GAP`: how tightly packed the icons are.
- `BOTTOM_MARGIN`: `0` makes the dock touch the bottom edge.
- `HIDE_WINDOWS_TASKBAR`: `false` keeps the real taskbar too.
- `SHOW_START_BUTTON`, `SHOW_CLOCK`, `SHOW_SOUND_BUTTON`.
- `AUTO_AUDIO`: `false` turns off the headset auto-switching.

Pinned apps and the chosen monitor are saved in `MiniDock.ini`.

## How it works

Every 300 ms it lists all top-level windows and keeps only the ones Windows itself would show on a taskbar: visible, not tool windows, not owned popups, not hidden ("cloaked") Store apps, and not on another virtual desktop. It groups them by the program (`.exe`) that owns them. Store apps all run inside `ApplicationFrameHost.exe`, so for those it looks at the window's inner part to find the real app.

The dock is a borderless, always-on-top window that never takes focus. That way it always knows which app you're actually using, and clicking it doesn't disturb anything. The dock is only rebuilt when an app opens or closes. Switching between apps just recolors the underlines.

The real taskbar is set to auto-hide (so Windows stops reserving the bottom strip) and then hidden.

## Known limits

- **No system tray icons** (Wi-Fi, OneDrive and so on). Sound has its own 🔊 button. Use **Win+A** for quick settings and **Win+N** for notifications.
- Windows of apps running **as administrator** can't be switched to unless MiniDock also runs as admin.
- The dock floats over the very bottom of maximized windows.
- If MiniDock gets force-killed and the taskbar doesn't come back, run `RestoreTaskbar.ahk`.
