#!/usr/bin/env bash
# deploy.sh — copy project files to their live locations and restart services
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"

echo "Deploying display-daemon..."
cp "$REPO/bin/display-daemon" ~/bin/display-daemon
chmod +x ~/bin/display-daemon

echo "Deploying audio-sync-web..."
cp "$REPO/bin/audio-sync-web" ~/bin/audio-sync-web
chmod +x ~/bin/audio-sync-web

echo "Deploying fb-capture..."
cp "$REPO/bin/fb-capture" ~/bin/fb-capture
chmod +x ~/bin/fb-capture

echo "Deploying Bluetooth speaker helper + agent..."
cp "$REPO/bin/bt-speaker-init.sh" ~/bin/bt-speaker-init.sh
cp "$REPO/bin/bt-speaker-agent" ~/bin/bt-speaker-agent
chmod +x ~/bin/bt-speaker-init.sh ~/bin/bt-speaker-agent

echo "Deploying pi8-audioctl (CLI debug)..."
cp "$REPO/bin/pi8-audioctl" ~/bin/pi8-audioctl
chmod +x ~/bin/pi8-audioctl

echo "Deploying pi8_presets + pi8_audio_http + pi8-audio-tui..."
cp "$REPO/bin/pi8_presets.py" ~/bin/pi8_presets.py
cp "$REPO/bin/pi8_audio_http.py" ~/bin/pi8_audio_http.py
cp "$REPO/bin/pi8-audio-tui" ~/bin/pi8-audio-tui
chmod +x ~/bin/pi8-audio-tui

echo "Deploying pi8-tty-dash (TTY1 status loop)..."
cp "$REPO/bin/pi8-tty-dash" ~/bin/pi8-tty-dash
chmod +x ~/bin/pi8-tty-dash
mkdir -p ~/.config
cp "$REPO/config/pi8-tty-login.sh" ~/.config/pi8-tty-login.sh

PROFILE_MARK='# >>> pi8-tty-login dashboard (deploy.sh)'
if [ -f "${HOME}/.bash_profile" ]; then
  hook_rc="${HOME}/.bash_profile"
else
  hook_rc="${HOME}/.profile"
fi
touch "$hook_rc"
if ! grep -qF "$PROFILE_MARK" "$hook_rc" 2>/dev/null; then
  cat >> "$hook_rc" <<'EOS'

# >>> pi8-tty-login dashboard (deploy.sh)
if [ -f "${HOME}/.config/pi8-tty-login.sh" ] && [ -r "${HOME}/.config/pi8-tty-login.sh" ]; then
  . "${HOME}/.config/pi8-tty-login.sh"
fi
# <<< pi8-tty-login
EOS
  echo "Appended TTY1 autostart hook to $hook_rc (login on tty1 only)."
fi

echo "Deploying ~/.config/pi8-audio-aliases.sh (alias audio → pi8-audio-tui)..."
cp "$REPO/config/pi8-audio-aliases.sh" ~/.config/pi8-audio-aliases.sh
ALIAS_MARK='# >>> pi8-audio aliases (deploy.sh)'
bashrc="${HOME}/.bashrc"
touch "$bashrc"
if ! grep -qF "$ALIAS_MARK" "$bashrc" 2>/dev/null; then
  cat >> "$bashrc" <<'EOS'

# >>> pi8-audio aliases (deploy.sh)
[ -r "${HOME}/.config/pi8-audio-aliases.sh" ] && . "${HOME}/.config/pi8-audio-aliases.sh"
# <<< pi8-audio aliases
EOS
  echo "Appended pi8-audio alias hook to $bashrc (open a new shell or: source ~/.bashrc)."
fi

echo "Deploying getty@tty1 autologin (sudo) — edit config/.../autologin.conf if user ≠ liu..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo cp "$REPO/config/systemd/getty@tty1.service.d/autologin.conf" \
  /etc/systemd/system/getty@tty1.service.d/autologin.conf
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1

echo "Deploying bluetooth.service drop-in (bluetoothd --noplugin=sap)..."
sudo mkdir -p /etc/systemd/system/bluetooth.service.d
sudo cp "$REPO/config/systemd/bluetooth.service.d/10-noplugin-sap.conf" \
  /etc/systemd/system/bluetooth.service.d/10-noplugin-sap.conf
sudo systemctl daemon-reload

echo "Deploying D-Bus policy for PipeWire/WirePlumber ↔ BlueZ (requires sudo)..."
sudo cp "$REPO/config/dbus-zz-pi8-bluetooth-wireplumber-policy.conf" \
  /etc/dbus-1/system.d/zz-pi8-bluetooth-wireplumber-policy.conf
sudo systemctl reload dbus
# Re-register BlueZ + PipeWire against the bus (reload alone can leave stale endpoint state).
sudo systemctl restart bluetooth
sleep 1.5
systemctl --user restart pipewire pipewire-pulse wireplumber || true

echo "Deploying pi8-bt-prefer-usb (system — USB dongle vs onboard)..."
sudo cp "$REPO/bin/pi8-bt-prefer-usb.sh" /usr/local/bin/pi8-bt-prefer-usb.sh
sudo chmod +x /usr/local/bin/pi8-bt-prefer-usb.sh
sudo cp "$REPO/config/systemd/pi8-bt-prefer-usb.service" /etc/systemd/system/pi8-bt-prefer-usb.service
sudo systemctl daemon-reload
sudo systemctl enable --now pi8-bt-prefer-usb.service

echo "Deploying /etc/pi8-audio/bluetooth-adapter (usb | onboard)..."
sudo mkdir -p /etc/pi8-audio
if [[ ! -f /etc/pi8-audio/bluetooth-adapter ]]; then
  echo "usb" | sudo tee /etc/pi8-audio/bluetooth-adapter >/dev/null
fi
sudo chmod 644 /etc/pi8-audio/bluetooth-adapter 2>/dev/null || true

echo "Deploying systemd units..."
cp "$REPO/systemd/"*.service ~/.config/systemd/user/
systemctl --user daemon-reload

echo "Restarting services..."
systemctl --user restart bt-speaker display-daemon audio-sync-web mpris-proxy

echo "Done. Status:"
systemctl --user is-active bt-speaker display-daemon audio-sync-web mpris-proxy
