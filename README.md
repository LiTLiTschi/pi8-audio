# pi8-audio

Raspberry Pi 4 audio system running on Ubuntu 24.04. Bluetooth A2DP receiver with multi-room output, HDMI display daemon, and a web UI for control.

## Architecture

```
Phone (BT A2DP) → BlueZ → PipeWire combine-sink → Wired speakers (front/rear)
                                                  → Bluetooth speaker
Phone (BT AVRCP) → mpris-proxy → playerctl → display-daemon
```

### Services

| Service | Port | Description |
|---|---|---|
| `audio-sync-web` | 8083 | Web UI — mode switching, outputs, display control |
| `display-daemon` | 8084 | HDMI display controller (localhost only) |
| `mpris-proxy` | — | BlueZ AVRCP → MPRIS2 bridge |

### Display modes

- **TTY** — raw Linux console
- **Now Playing** — cover art + title/artist overlay, animated crossfade
- **Visualizer** — 64-bar cava audio visualizer, purple→cyan gradient
- **Music Video** — yt-dlp YouTube search + mpv playback, auto-advances

## Setup

### Dependencies

```bash
sudo apt install -y mpv cava bluez playerctl
pip install Pillow yt-dlp
sudo usermod -aG video liu
```

### sudoers (VT switching)

```bash
echo 'liu ALL=(ALL) NOPASSWD: /usr/bin/chvt 1, /usr/bin/chvt 2' \
  | sudo tee /etc/sudoers.d/liu-display
sudo chmod 440 /etc/sudoers.d/liu-display
```

### Install

```bash
cp bin/display-daemon bin/audio-sync-web bin/bt-speaker-init.sh bin/bt-speaker-agent ~/bin/
chmod +x ~/bin/display-daemon ~/bin/audio-sync-web ~/bin/bt-speaker-init.sh ~/bin/bt-speaker-agent
cp systemd/*.service ~/.config/systemd/user/
cp config/display-config.example.json ~/.config/display-config.json
systemctl --user daemon-reload
systemctl --user enable --now bt-speaker display-daemon audio-sync-web mpris-proxy
```

Bluetooth visibility depends on **`bt-speaker`**: it runs `discoverable on` / `pairable on` and registers the `bt-speaker-agent` pairing helper. If you restart system **`bluetooth.service`** (Web UI or `sudo systemctl restart bluetooth`), also run `systemctl --user restart bt-speaker` after a second or two, or use **deploy.sh** / restart **`bt-speaker`** so init runs again (BlueZ can return *Busy* immediately after `bluetoothd` restarts).

The adapter **friendly name** comes from BlueZ’s hostname plugin (`PRETTY_HOSTNAME` in **`/etc/machine-info`**) and a persisted **alias** under **`/var/lib/bluetooth/<adapter>/settings`**. `bt-speaker-init.sh` sets **`bluetoothctl system-alias`** to the **static hostname** (`hostnamectl --static`) so the radio name stays **`pi8`** (or whatever `/etc/hostname` is) and does not stick on an old value.

### SoundCloud cover art (optional)

Register a free app at https://soundcloud.com/you/apps, then:
```bash
# Edit ~/.config/display-config.json
{ "soundcloud_client_id": "YOUR_CLIENT_ID" }
systemctl --user restart display-daemon
```

## Hardware

- Raspberry Pi 4 (4GB), Ubuntu 24.04 LTS aarch64
- HDMI connected to 4K display (card1-HDMI-A-2, 3840×2160)
- Wired speakers: front (USB DAC) + rear (3.5mm BCM2835)
- Bluetooth speaker (for bedroom)
- Android phone as BT source

## Web UI

Open `http://pi8:8083` — on mobile: tab bar (🎵 Audio / 🖥 Display); on desktop (≥900px): two-column layout.
