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

The daemon switches to a **blank VT** for HDMI (`PI8_BLANK_VT`, default **2**) and back to the **console VT** where autologin runs (`PI8_CONSOLE_VT`, default **1**). If your login session is not on VT1, set the env vars on the **`display-daemon`** service (or shell) and grant `chvt` for those numbers.

```bash
echo 'liu ALL=(ALL) NOPASSWD: /usr/bin/chvt 1, /usr/bin/chvt 2' \
  | sudo tee /etc/sudoers.d/liu-display
sudo chmod 440 /etc/sudoers.d/liu-display
# If using e.g. PI8_CONSOLE_VT=7 PI8_BLANK_VT=8, add: /usr/bin/chvt 7, /usr/bin/chvt 8
```

**4K / smooth motion (optional env on `display-daemon`):** `PI8_VIS_FRAMERATE` (default 72, fullscreen cava), `PI8_NP_CAVA_FRAMERATE` (default 90, cover spectrum input), `PI8_NP_OVERLAY_MAX_HZ` (default 48, caps JPEG+mpv pushes — raise on a fast board, lower if the Pi pegs CPU), `PI8_NP_JPEG_QUALITY` (default 92).

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

**D-Bus / A2DP:** If the phone sees **pi8** but **cannot connect**, check `journalctl -u dbus` for `Rejected send message ... MediaEndpoint1.Error.NotImplemented` (WirePlumber → `bluetoothd`). Stock system policy only allows `error` / `method_return` when `send_requested_reply=true`; BlueZ negotiation uses `requested_reply=0`, and those messages have `interface="(unset)"`, so **`send_interface` rules do not apply**—the policy must include `<allow send_type="error"/>` and `<allow send_type="method_return"/>`. **`deploy.sh`** installs **`config/dbus-zz-pi8-bluetooth-wireplumber-policy.conf`**, reloads D-Bus, restarts **`bluetooth`**, and restarts user **`pipewire`** / **`wireplumber`** so endpoints re-register. If problems persist after deploy, reboot once or run `sudo systemctl restart dbus` (brief disruption) and restart **`bluetooth`** again.

### Bluetooth: range, RF, and “invisible until I’m close”

The onboard Pi adapter uses **2.4 GHz**. **Distance and noise** matter more than many BlueZ settings. If **pi8** does not show up or will not connect from across the room but **works when the phone is close** (~1 m, line of sight), treat it as **RF first**: move the phone closer for pairing/reconnect, try another board orientation or case (metal lids hurt), and know that **USB3** storage and cables can raise the noise floor—**short/shielded USB3 cables** or **ferrite clamps** on the cable can help if you cannot unplug the drive.

**CLI (no web UI cache issues):** `pi8-audioctl status` — full stack snapshot; `pi8-audioctl restart-bt` after changing BlueZ.

**HCI capture:** `sudo btmon` may **crash** on some **Cypress** controllers (known BlueZ `btmon` bug around Index Info). Use **`sudo hcidump -i hci0 -X`** instead. An empty capture during a phone scan can mean no traffic reached the controller—combine with proximity tests above.

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

**Minimal phone page:** `http://pi8:8083/m` — display mode only + **scenes** (no volume or calibration). **Scenes** live in `~/.config/pi8-presets.json` (display + audio bundle). Manage them on the Pi with **`pi8-audio-tui`** (↑↓ Enter apply, `n`/`d`/`[`/`]`, `e` opens `$EDITOR`, `a` toggles `audio_profile` simple↔multi via the API). After **`deploy.sh`**, **`audio`** is a shell alias for that TUI (hook in `~/.bashrc` → `~/.config/pi8-audio-aliases.sh`); run **`source ~/.bashrc`** once if the alias is missing. **`audio_profile`:** `simple` = Bluetooth (and default sink) to HDMI without PipeWire `combine-stream`; `multi` = previous multi-output + combined sink behavior. Legacy **audio presets** in the full UI still use the nested `presets` object inside `~/.config/audio-sync.json` (unrelated to scene file).
