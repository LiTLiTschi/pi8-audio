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

echo "Deploying D-Bus policy for PipeWire/WirePlumber ↔ BlueZ (requires sudo)..."
sudo cp "$REPO/config/dbus-zz-pi8-bluetooth-wireplumber-policy.conf" \
  /etc/dbus-1/system.d/zz-pi8-bluetooth-wireplumber-policy.conf
sudo systemctl reload dbus

echo "Deploying systemd units..."
cp "$REPO/systemd/"*.service ~/.config/systemd/user/
systemctl --user daemon-reload

echo "Restarting services..."
systemctl --user restart bt-speaker display-daemon audio-sync-web mpris-proxy

echo "Done. Status:"
systemctl --user is-active bt-speaker display-daemon audio-sync-web mpris-proxy
