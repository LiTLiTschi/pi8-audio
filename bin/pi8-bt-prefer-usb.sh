#!/bin/bash
# Select which Bluetooth controller is active (UART/onboard vs USB dongle).
# Reads /etc/pi8-audio/bluetooth-adapter: first line usb | onboard (default: usb).
#   usb     — when a USB BT dongle exists: UART hci down, USB hci up; else UART only.
#   onboard — USB hci down, UART up (ignore dongle for pairing/audio).
# Must run as root (hciconfig). systemd: BindsTo bluetooth.service.

set -euo pipefail

CONF=${PI8_BT_ADAPTER_CONF:-/etc/pi8-audio/bluetooth-adapter}
mode=usb
if [[ -f "$CONF" ]]; then
  mode=$(head -1 "$CONF" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
fi
[[ "$mode" == "onboard" ]] || mode=usb

declare -a usb=()
declare -a uart=()

for d in /sys/class/bluetooth/hci*; do
  [[ -e "$d" ]] || continue
  idx="$(basename "$d")"
  [[ "$idx" =~ ^hci[0-9]+$ ]] || continue
  line="$(hciconfig "$idx" 2>/dev/null | head -1 || true)"
  [[ -n "$line" ]] || continue
  if [[ "$line" == *'Bus: USB'* ]]; then
    usb+=("$idx")
  else
    uart+=("$idx")
  fi
done

if [[ "$mode" == "onboard" ]]; then
  for h in "${usb[@]}"; do
    hciconfig "$h" down 2>/dev/null || true
  done
  for h in "${uart[@]}"; do
    hciconfig "$h" up 2>/dev/null || true
  done
else
  if ((${#usb[@]} > 0)); then
    for h in "${uart[@]}"; do
      hciconfig "$h" down 2>/dev/null || true
    done
    for h in "${usb[@]}"; do
      hciconfig "$h" up 2>/dev/null || true
    done
  else
    for h in "${uart[@]}"; do
      hciconfig "$h" up 2>/dev/null || true
    done
  fi
fi
