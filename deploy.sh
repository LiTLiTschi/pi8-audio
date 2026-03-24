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

echo "Deploying systemd units..."
cp "$REPO/systemd/"*.service ~/.config/systemd/user/
systemctl --user daemon-reload

echo "Restarting services..."
systemctl --user restart display-daemon audio-sync-web mpris-proxy

echo "Done. Status:"
systemctl --user is-active display-daemon audio-sync-web mpris-proxy
