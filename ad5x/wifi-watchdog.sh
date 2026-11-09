#!/bin/sh
# AD5X Wi-Fi watchdog. Needs root on the printer (e.g. via ZMOD).
# Turns off Wi-Fi power saving, then checks the connection every minute
# and reconnects if it has dropped. Written for busybox sh.
#
# Run:   sh wifi-watchdog.sh &
# Undo:  kill the process (see README). It changes nothing permanently;
#        power saving comes back on at the next reboot.

IFACE="${IFACE:-wlan0}"
INTERVAL="${INTERVAL:-60}"      # seconds between checks
FAILS_BEFORE_FIX="${FAILS_BEFORE_FIX:-3}"
LOG="${LOG:-/tmp/wifi-watchdog.log}"

log() {
  echo "$(date '+%F %T') $*" >> "$LOG"
  # keep the log small
  if [ "$(wc -c < "$LOG")" -gt 100000 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  fi
}

power_save_off() {
  if command -v iw >/dev/null 2>&1; then
    iw dev "$IFACE" set power_save off 2>/dev/null && log "power save off (iw)" && return
  fi
  if command -v iwconfig >/dev/null 2>&1; then
    iwconfig "$IFACE" power off 2>/dev/null && log "power save off (iwconfig)" && return
  fi
  log "could not turn off power save (no iw/iwconfig)"
}

gateway() {
  ip route 2>/dev/null | awk '/^default/ {print $3; exit}'
}

online() {
  gw="$(gateway)"
  [ -n "$gw" ] && ping -c 1 -W 3 "$gw" >/dev/null 2>&1
}

reconnect() {
  log "connection lost, reconnecting"
  if command -v wpa_cli >/dev/null 2>&1; then
    wpa_cli -i "$IFACE" reconnect >/dev/null 2>&1
    sleep 15
    online && { log "back online (wpa_cli reconnect)"; return; }
  fi
  ip link set "$IFACE" down; sleep 2; ip link set "$IFACE" up
  if command -v udhcpc >/dev/null 2>&1; then
    udhcpc -i "$IFACE" -n -q >/dev/null 2>&1
  fi
  sleep 15
  if online; then
    log "back online (interface restart)"
  else
    log "still offline"
  fi
  power_save_off
}

log "watchdog started on $IFACE"
power_save_off
fails=0
while true; do
  if online; then
    fails=0
  else
    fails=$((fails + 1))
    log "check failed ($fails/$FAILS_BEFORE_FIX)"
    if [ "$fails" -ge "$FAILS_BEFORE_FIX" ]; then
      reconnect
      fails=0
    fi
  fi
  sleep "$INTERVAL"
done
