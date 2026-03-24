#!/bin/bash
# Re-applies adapter settings after bluetoothd start/restart. BlueZ often returns
# org.bluez.Error.Busy for a short window — retry power on, but always attempt
# discoverable/pairable (adapter may already be powered when power on errors).
set -euo pipefail
for _ in $(seq 1 40); do
  bluetoothctl power on && break || sleep 0.25
done
bluetoothctl discoverable on
bluetoothctl pairable on
# Adapter alias is stored under /var/lib/bluetooth; keep it aligned with static
# hostname so a removed PRETTY_HOSTNAME or old name does not linger (e.g. "Pie").
hn="$(hostnamectl --static 2>/dev/null || hostname)"
if [[ -n "$hn" ]]; then
  bluetoothctl system-alias "$hn" || true
fi
