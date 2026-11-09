# AD5X Wi-Fi drop fix

## 1. Router fixes (no mod, try these first)
- [ ] Give the printer its own **2.4 GHz-only** network (or split 2.4/5 GHz names)
- [ ] Turn off **band steering / smart connect** for that network
- [ ] **Reserve a fixed IP** for the printer (DHCP reservation)
- [ ] Use channel **1, 6 or 11** and 20 MHz width on 2.4 GHz
- [ ] Turn off any "kick weak clients" / airtime fairness option
- [ ] Printer within reasonable range of the router or mesh node

Leave it 48 h. If it still drops, try step 2.

## 2. Watchdog script (needs root, e.g. ZMOD)
`wifi-watchdog.sh` turns off Wi-Fi power saving and reconnects
automatically if the printer loses the router for 3 minutes.

Copy it to the printer, then:

    sh /path/to/wifi-watchdog.sh &

Check what it did:

    cat /tmp/wifi-watchdog.log

Settings (optional, set before the command):
`IFACE=wlan0 INTERVAL=60 FAILS_BEFORE_FIX=3`

### Undo
    kill $(pgrep -f wifi-watchdog.sh)

Nothing is changed permanently: a reboot puts everything back.
Auto-start on boot is not set up yet. That depends on how ZMOD
runs custom scripts; to be added once tested on a real printer.

## Untested
Not yet run on an AD5X. Things to confirm on the printer:
- Wi-Fi interface name (`ip link` — expected `wlan0`)
- Which of `iw`, `iwconfig`, `wpa_cli`, `udhcpc` exist
