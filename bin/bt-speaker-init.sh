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
