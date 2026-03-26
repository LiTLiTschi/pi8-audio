#!/bin/bash
# Re-applies adapter settings after bluetoothd start/restart. BlueZ often returns
# org.bluez.Error.Busy for a short window — retry power on, but always attempt
# discoverable/pairable (adapter may already be powered when power on errors).
#
# USB dongle vs onboard: see /etc/pi8-audio/bluetooth-adapter (usb | onboard).
# systemd runs pi8-bt-prefer-usb.sh first (hciconfig). Do not run bluetoothctl power on
# in usb+dongle mode — it turns the Cypress radio back on (BlueZ quirk).

set -euo pipefail

_bt_mode=usb
if [[ -r /etc/pi8-audio/bluetooth-adapter ]]; then
  _bt_mode=$(head -1 /etc/pi8-audio/bluetooth-adapter | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
fi
[[ "$_bt_mode" == "onboard" ]] || _bt_mode=usb

_bt_have_usb=0

# Classify Primary controllers and point bluetoothctl at the right MAC.
_pick_bt_controller() {
  local dir idx line0 mac dev
  local -a usb_macs=()
  local -a int_macs=()

  for dir in /sys/class/bluetooth/hci*; do
    [[ -e "$dir" ]] || continue
    idx="$(basename "$dir")"
    [[ "$idx" =~ ^hci[0-9]+$ ]] || continue

    line0="$(hciconfig "$idx" 2>/dev/null | head -1 || true)"
    [[ -n "$line0" ]] || continue
    mac="$(hciconfig "$idx" 2>/dev/null | awk '/BD Address/ {print $3; exit}' || true)"
    [[ -n "$mac" ]] || continue
    mac="$(tr '[:lower:]' '[:upper:]' <<<"$mac")"

    if [[ "$line0" == *'Bus: USB'* ]]; then
      usb_macs+=("$mac")
    else
      dev="$(readlink -f "$dir/device" 2>/dev/null || true)"
      if [[ "$dev" == *"/usb"* ]]; then
        usb_macs+=("$mac")
      else
        int_macs+=("$mac")
      fi
    fi
  done

  if ((${#usb_macs[@]} > 0)); then
    _bt_have_usb=1
  fi
  if [[ "$_bt_mode" == "onboard" ]]; then
    if ((${#int_macs[@]} > 0)); then
      bluetoothctl select "${int_macs[0]}" 2>/dev/null || true
    elif ((${#usb_macs[@]} > 0)); then
      bluetoothctl select "${usb_macs[0]}" 2>/dev/null || true
    fi
  else
    if ((${#usb_macs[@]} > 0)); then
      bluetoothctl select "${usb_macs[0]}" 2>/dev/null || true
    elif ((${#int_macs[@]} > 0)); then
      bluetoothctl select "${int_macs[0]}" 2>/dev/null || true
    fi
  fi
}

_pick_bt_controller

# BlueZ "Powered" must be yes for pairing; hciconfig may be UP after
# pi8-bt-prefer-usb.service, but a bluetoothd restart can leave Powered=no until
# power on. We already selected the right controller (USB vs onboard), so power on
# targets that adapter only — it does not bring UART back if that hci stayed down.
if [[ "$_bt_mode" == "usb" ]] && ((_bt_have_usb)); then
  for _ in $(seq 1 25); do
    bluetoothctl power on && break || sleep 0.2
  done
else
  for _ in $(seq 1 40); do
    bluetoothctl power on && break || sleep 0.25
  done
fi

# 0 = no auto-timeout (stay discoverable until turned off)
bluetoothctl discoverable-timeout 0 || true
bluetoothctl discoverable on || true
bluetoothctl pairable on
# Friendly name: /etc/pi8-audio/bluetooth-alias (UTF-8, first line) overrides hostname.
# Empty/missing file → static hostname (avoids stale PRETTY_HOSTNAME in BlueZ).
bt_alias=""
if [[ -r /etc/pi8-audio/bluetooth-alias ]]; then
  bt_alias="$(head -1 /etc/pi8-audio/bluetooth-alias | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
fi
if [[ -n "$bt_alias" ]]; then
  bluetoothctl system-alias "$bt_alias" || true
else
  hn="$(hostnamectl --static 2>/dev/null || hostname)"
  if [[ -n "$hn" ]]; then
    bluetoothctl system-alias "$hn" || true
  fi
fi
