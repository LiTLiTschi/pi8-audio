# Display Daemon — Design Spec

**Date:** 2026-03-23
**Project:** pi8 audio-system
**Status:** Approved

---

## Overview

Add HDMI display control to the audio system. A new `display-daemon` Python service manages what is shown on the connected HDMI screen (HDMI 0). Four modes are supported:

- **Off** — show the raw Linux TTY console (current default behaviour)
- **Now Playing** — full-screen cover art with optional fancy title/artist text overlay; animated crossfade between tracks
- **Visualizer** — real-time audio-reactive bar visualizer reading from PipeWire combined sink monitor
- **Music Video** — auto-search YouTube for the current BT track, play with Pi audio, auto-advance queue

The Web UI (audio-sync-web, port 8083) gains a "Display" panel to control modes. The daemon runs as a separate systemd user service.

---

## Architecture

```
Phone (BT) ──AVRCP──► BlueZ ──MPRIS──► playerctl
                                            │
                                     display-daemon (localhost:8084)
                                            │
                     ┌───────────┬──────────┼────────────────┐
                   off      now-playing  visualizer     music-video
                     │           │            │               │
                  chvt 1    Pillow PNG     cava +         yt-dlp search
                   (TTY)    crossfade    Pillow frames    → mpv IPC
                            → mpv IPC   → /dev/fb0
                                 │             │
                        mpv --vo=drm        mpv NOT
                    (long-lived process)    running
                IPC: /tmp/mpv-display.sock
```

**audio-sync-web** proxies display commands from the browser to display-daemon. The browser never talks directly to port 8084.

---

## Components

### 1. `~/bin/display-daemon` (new Python script)

Uses system Python3 (same as audio-sync-web). Dependencies installed into `~/.venv`:

```bash
uv pip install Pillow yt-dlp
```

**Threads and synchronisation:**
- **HTTP thread:** stdlib `http.server.BaseHTTPRequestHandler` in a `threading.Thread` (same pattern as audio-sync-web). Handles GET `/state` and POST `/set`. Returns `400 {"error": "invalid mode"}` for unknown mode values.
- **MPRIS metadata watcher thread:** runs `playerctl -F metadata` as subprocess, reads stdout line by line. Collects lines for 200ms (debounce window) then enqueues a single `MetadataEvent` onto the shared `queue.Queue`. This handles playerctl flushing multiple key lines per track change as a single logical event.
- **MPRIS status watcher thread:** runs `playerctl -F status` as subprocess, reads play/pause/stop state. Puts `StatusEvent` onto the same shared `queue.Queue`. Does NOT re-trigger rendering or yt-dlp search.
- **Display controller thread:** the only thread that consumes from the queue, drives mpv and Pillow, and updates shared state.
- **Shared state** (`mode`, `overlay_enabled`, `visualizer_mirror`, current track, current status string) protected by a single `threading.Lock`. Only the display controller writes; HTTP thread reads under the lock.

### 2. `~/.config/systemd/user/display-daemon.service` (new)

Standard user service. `After=pipewire.service`. `Restart=on-failure`.

```ini
[Unit]
Description=HDMI Display Daemon
After=pipewire.service

[Service]
ExecStart=/home/liu/bin/display-daemon
Restart=on-failure
Environment=PATH=/home/liu/.venv/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
```

### 3. audio-sync-web additions

- New "Display" collapsible panel in the Web UI services section
- Two new endpoints: `GET /display-state`, `POST /display`
- Both proxy to `http://localhost:8084`

---

## VT / Display Switching

mpv `--vo=drm` takes DRM master and renders to the physical screen regardless of which VT is active. However, the TTY console (VT1) renders character text on top of the framebuffer which bleeds through. The Pillow framebuffer writes for the visualizer have the same bleed problem. Therefore **all non-off modes require `chvt 2`**:

- **Activating display** (any mode → now-playing, visualizer, or music-video): `sudo chvt 2` before starting mpv or framebuffer writes. VT2 is blank.
- **Deactivating** (mode → off): stop mpv / cava, then `sudo chvt 1` to restore the console.

`chvt` requires `CAP_SYS_TTY_CONFIG`. Add to `/etc/sudoers.d/liu-display`:
```
liu ALL=(ALL) NOPASSWD: /usr/bin/chvt 1, /usr/bin/chvt 2
```
Restricting to arguments `1` and `2` limits the blast radius of the sudoers rule.

`sudo NOPASSWD` works from systemd user services (no TTY needed, no PAM interaction required when `NOPASSWD` is set).

---

## mpv Process Management

mpv is **only used in now-playing and music-video modes** — not in visualizer mode. It is a single long-lived process, started when entering now-playing or music-video mode, and stopped when leaving to off or visualizer.

**Launch command:**
```bash
mpv --vo=drm --drm-connector=HDMI-A-1 --fullscreen \
    --input-ipc-server=/tmp/mpv-display.sock \
    --no-terminal --idle=yes \
    --ao=pipewire --audio-device=pipewire/combined \
    --loop-file=inf \
    --image-display-duration=inf \
    /tmp/now-playing.png
```

**Switching content:** send `loadfile` via the IPC socket:
```json
{"command": ["loadfile", "/tmp/now-playing.png", "replace"]}
{"command": ["loadfile", "https://youtube-stream-url", "replace"]}
```

**Stopping playback** (user skips on phone mid-video): send `{"command": ["stop"]}` via IPC. mpv keeps running idle.

**Quitting** (mode → off or visualizer): send `{"command": ["quit"]}`, wait for process exit, then `sudo chvt 1` (if going to off) or leave on VT2 (if going to visualizer).

**Orphan cleanup:** on daemon startup, kill any existing process matching `--input-ipc-server=/tmp/mpv-display.sock` before launching a fresh one.

**Audio routing:** `--ao=pipewire --audio-device=pipewire/combined` routes video audio through the combined PipeWire sink. The device name `combined` must match `node.name` in `~/.config/pipewire/pipewire.conf.d/combined.conf` (currently `"combined"`). If that name ever changes, this flag must be updated to match.

When switching to music-video mode, `playerctl pause` is called to stop Bluetooth audio before mpv starts. The window between `playerctl pause` and mpv starting audio (~2–5s during yt-dlp search) means a brief silence — this is acceptable and intentional.

---

## Now-Playing Renderer

Triggered on every `MetadataEvent` with a changed title or artist while mode is `now-playing`.

`StatusEvent` handling:
- `Playing` or `Paused` → update in-memory status field only; no re-render. The `status` API field reports `"playing"` for both (pause state is not exposed separately).
- `Stopped` or no player → **does** trigger a re-render: write an all-black PNG to `/tmp/now-playing.png` and send `loadfile` to mpv. This is an exception to the "no re-render on StatusEvent" rule.

### Rendering pipeline

1. Read `mpris:artUrl`, `xesam:title`, `xesam:artist` from the event
2. Download cover art to `/tmp/display-cover.jpg` — only if the URL differs from the last download
3. Render full-screen PNG with Pillow at detected screen resolution (see below):
   - **Layer 1 — blurred background:** cover art scaled to fill screen, `ImageFilter.GaussianBlur(radius=40)`, blended with black at alpha=0.5
   - **Layer 2 — cover art:** sharp, centred, height = 55% of screen height; drop shadow as a separate blurred black layer offset by (0, 8px) beneath
   - **Layer 3 — text overlay** (if `overlay_enabled == True`):
     - Artist: Noto Sans Regular 36px, colour `#CCCCCC`, centred horizontally
     - Title: Noto Sans Bold 56px, colour `#FFFFFF`; drop shadow by drawing twice (offset 2/2px in black, then white on top)
     - Positions: title at 78% of screen height, artist at 85%
     - Font paths: `/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf` and `NotoSans-Bold.ttf`. Fallback: first `.ttf` found under `/usr/share/fonts/`. Final fallback: PIL built-in default.
4. Save as `/tmp/now-playing-new.png`
5. Apply crossfade (see below)

**Fallbacks:**
- `artUrl` empty or download fails: black background, skip Layer 1 and 2, text only (or black if overlay off)
- No player / status = Stopped: render all-black PNG, loadfile to mpv
- `xesam:artist` is an array (e.g. `['Queen']`): join with `, `

**Screen resolution detection:**
```python
for connector in ["card0-HDMI-A-1", "card0-HDMI-A-2"]:
    path = f"/sys/class/drm/{connector}/modes"
    # read first line, parse "WxH"
```
`card0-HDMI-A-1` = physical HDMI port 0 (target). `card0-HDMI-A-2` = physical HDMI port 1 (fallback). Falls back to 1920×1080 if neither is readable.

### Crossfade transition

To avoid a file-write race condition (mpv reads the file while Pillow writes it), all crossfade frames are **fully pre-rendered to numbered temp files** before any are sent to mpv:

1. Keep the previous frame as `old_frame` (Pillow `Image` object in memory)
2. Render new frame as `new_frame`
3. Pre-render 20 blend frames to `/tmp/cf/frame-00.png` … `frame-19.png`. On the very first track (no previous frame), use an all-black image of the same dimensions as `old_frame`:
   ```python
   old_frame = old_frame or Image.new("RGB", (width, height), (0, 0, 0))
   for i in range(20):
       alpha = (i + 1) / 20
       blend = Image.blend(old_frame, new_frame, alpha)
       blend.save(f"/tmp/cf/frame-{i:02d}.png")
   ```
4. Loadfile each frame sequentially via mpv IPC, sleeping `1/30` s between frames (~0.67s total)
5. After the loop, copy `new_frame` to `/tmp/now-playing.png` and loadfile it as the stable frame
6. Delete `/tmp/cf/frame-*.png`

The `/tmp/cf/` directory is created on daemon startup if absent.

MPRIS events received during crossfade are queued. The display controller processes them immediately after the crossfade loop completes.

---

## Visualizer Mode

A real-time audio-reactive bar visualizer rendered directly to the framebuffer using `cava` + Pillow. **mpv does not run in this mode.**

### cava configuration

Written to `/tmp/cava-display.conf` on mode activation:

```ini
[general]
bars = 64
framerate = 30

[input]
method = pipewire
source = combined.monitor

[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 1000
```

`source = combined.monitor` targets the PipeWire monitor of the combined sink (node name `combined` as set in `combined.conf`). This ensures the visualizer reacts to all audio routed through the combined sink. If `combined.monitor` is not found, cava falls back to the default monitor automatically.

### Pillow rendering per frame

1. Parse cava stdout: each line is 64 space-separated integers (0–1000)
2. Create black background image at framebuffer dimensions (see below)
3. Draw 64 bars, evenly spaced:
   - Bar height: `bar_value / 1000 * canvas_height`
   - Bottom-anchored (or top+bottom meeting in middle if `visualizer_mirror == True`)
   - Colour: linear interpolation from `#4B0082` (deep purple, bottom) to `#00FFFF` (cyan, top) based on normalised bar height
   - Bar width: 60% of slot width
4. Write frame to `/dev/fb0`

### Writing to `/dev/fb0`

**Permissions:** `/dev/fb0` is owned by `root:video`. Add `liu` to the `video` group:
```bash
sudo usermod -aG video liu
# log out and back in, or restart the user session
```
The daemon logs a clear error and sets `status = "fb_permission_error"` if the open fails.

```python
import mmap, os

fb_fd = os.open("/dev/fb0", os.O_RDWR)
fb = mmap.mmap(fb_fd, 0)  # maps entire framebuffer

# per frame:
fb.seek(0)
fb.write(frame_bytes)
```

Using `mmap` avoids repeated `open()`/`close()` overhead. `mmap` is opened once on visualizer mode entry and closed on exit.

**Clearing stale frame on visualizer exit:** before starting mpv (transition to now-playing/music-video) or before `chvt 1` (transition to off), write a full black frame to erase the last visualizer frame:
```python
fb.seek(0)
fb.write(b"\x00" * (width * height * bpp_bytes))
```
Then close the mmap and wait for mpv process to be ready before issuing `loadfile`.

**Framebuffer geometry detection** (done once on mode entry):
```python
vsize = open("/sys/class/graphics/fb0/virtual_size").read().strip()  # "1920,1080"
bpp   = int(open("/sys/class/graphics/fb0/bits_per_pixel").read())   # 32
```
Width and height from `virtual_size`. Pixel format: 32bpp on Pi is typically BGRA. Pillow canvas uses mode `RGBA`; convert with `frame.convert("RGBA")` then swap R/B channels to match BGRA if needed (verify at runtime by testing a known-colour frame).

---

## Music Video Mode

Triggered on every `MetadataEvent` with a changed title or artist while mode is `music-video`. `StatusEvent` does not re-trigger search.

### Flow

```
MetadataEvent (new title/artist)
    │
    ├─ yt-dlp --no-playlist --print url --quiet
    │       "ytsearch1:{artist} {title} official music video"
    │       (`--print url` singular — prints direct stream URL)
    │       take FIRST non-empty line only; 15s timeout; exception or empty = not found
    │       │
    │   found URL ──► playerctl pause        (stop phone audio)
    │                 skip_count = 0         (reset on video start)
    │                 mpv loadfile <url> replace
    │                 wait for mpv "end-file" IPC event (see below)
    │                 on video ends normally:
    │                     playerctl next     (AVRCP next; phone auto-plays next track)
    │                     wait up to 5s for new MetadataEvent
    │                     if no event arrives: call playerctl play  ← resume only, NOT next again
    │                 (next MetadataEvent triggers loop again)
    │
    └─ not found
            skip_count++
            if skip_count >= 5:
                mode = "now-playing"
                status = "no_videos_found"
                persist state
            else:
                playerctl next
                wait for next MetadataEvent
```

**`skip_count` semantics:**
- Incremented only on yt-dlp failure (empty result or exception)
- Reset to 0 on any successful video start
- Phone-initiated skips (MetadataEvent while video is playing) do NOT increment skip_count; they trigger `{"command": ["stop"]}` to mpv then restart the loop for the new track

**After `playerctl next` on normal video end:** the "wait 5s + playerctl play" fallback handles the edge case where the phone's player does not auto-start after AVRCP next when paused. `playerctl play` resumes playback; the phone then emits a new MetadataEvent to restart the loop. This path does NOT call `playerctl next` a second time.

**mpv end-file detection via IPC:** after `loadfile`, the display controller thread reads from the mpv IPC socket in a loop, parsing newline-delimited JSON objects. The video has ended when an object with `"event": "end-file"` is received. The read loop runs in the display controller thread (blocking while video plays). `MetadataEvents` that arrive during playback are still enqueued by the watcher thread; the display controller processes them immediately after exiting the read loop. If the IPC socket read returns an error or the socket closes unexpectedly, treat it as end-of-file.

**mpv process exit race on visualizer transition:** when switching from visualizer to now-playing/music-video, the framebuffer mmap is closed and a blank black frame is written. Then mpv is launched. Wait for the mpv IPC socket to appear (poll with 100ms interval, 5s timeout) before issuing the first `loadfile` command, ensuring mpv is ready to receive commands.

---

## MPRIS Metadata Parsing

`playerctl -F metadata` outputs one line per metadata key per event:
```
<player>   <key>   <value>
```

Lines arrive in bursts (one burst = one track change). The 200ms debounce window in the watcher thread coalesces a burst into a single `MetadataEvent` dict:
```python
{
  "artUrl":  "...",
  "title":   "Bohemian Rhapsody",
  "artist":  "Queen",   # arrays stripped: ['Queen'] → 'Queen'
}
```

Keys of interest: `mpris:artUrl`, `xesam:title`, `xesam:artist`.
`xesam:artist` may be serialised as `['Name']` — strip leading `['`, trailing `']`, and inner quotes, then split on `', '` and rejoin with `', '`.

A `MetadataEvent` only triggers re-render / video search when `title` or `artist` differs from the last rendered values.

---

## Persisted State

`~/.config/display-state.json`:
```json
{
  "mode": "off",
  "overlay_enabled": true,
  "visualizer_mirror": false
}
```

Track metadata is **not** persisted. On daemon restart:
1. Restore `mode`, `overlay_enabled`, `visualizer_mirror` from JSON (defaults if file absent)
2. Render idle screen (black) and start mpv if mode is now-playing or music-video
3. Wait for next MPRIS event to populate content

---

## Web UI — Display Panel

Location: collapsible panel in the services section.

```
┌───────────────────────────────────────────────┐
│ 🖥 Display                                [▼] │
├───────────────────────────────────────────────┤
│  [ TTY ] [ Now Playing ] [ Visualizer ] [Video]│
│                                               │
│  ☑ Show title / artist overlay                │  ← only visible in Now Playing
│  ☑ Mirror bars                                │  ← only visible in Visualizer
│                                               │
│  ● Playing: Bohemian Rhapsody — Queen         │  ← status line, polls every 3s
└───────────────────────────────────────────────┘
```

**Status line values** (from `status` field):
| `status` value | Displayed text |
|----------------|----------------|
| `"idle"` | "No player connected" |
| `"playing"` | "Playing: {title} — {artist}" |
| `"searching"` | "Searching for video…" |
| `"no_videos_found"` | "No videos found — switched to Now Playing" |
| `"cava_unavailable"` | "cava not installed — visualizer unavailable" |
| `"fb_permission_error"` | "Framebuffer error — add liu to video group" |
| `"daemon_down"` | "Display service unavailable" |

When daemon is unreachable, audio-sync-web returns:
```json
{"mode": "off", "overlay_enabled": true, "visualizer_mirror": false, "status": "daemon_down", "track": null}
```
The `"daemon_down"` status distinguishes this from a genuine `mode: "off"`. The UI shows TTY as active but greys out mode buttons with a warning.

---

## API

### display-daemon (localhost:8084, internal only)

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/state` | — | `{mode, overlay_enabled, visualizer_mirror, track: {title, artist}\|null, status}` |
| POST | `/set` | `{mode?, overlay_enabled?, visualizer_mirror?}` | `200 {ok: true}` or `400 {error: "invalid mode"}` |

`mode` values: `"off"`, `"now-playing"`, `"visualizer"`, `"music-video"`

`status` values:
| Value | Meaning |
|-------|---------|
| `"idle"` | Mode active but no player connected / nothing playing |
| `"playing"` | Track playing or paused (pause not distinguished) |
| `"searching"` | yt-dlp search in progress |
| `"no_videos_found"` | 5 consecutive tracks had no video; reverted to now-playing |
| `"cava_unavailable"` | `cava` binary not found; visualizer mode cannot start |
| `"fb_permission_error"` | `/dev/fb0` open failed; `liu` likely not in `video` group |

### audio-sync-web additions (port 8083)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/display-state` | Proxies to display-daemon `/state`; returns `{status: "daemon_down", ...}` if unreachable |
| POST | `/display` | Proxies to display-daemon `/set`; forwards 4xx responses unchanged |

---

## New Files

| Path | Purpose |
|------|---------|
| `~/bin/display-daemon` | Main daemon script |
| `~/.config/systemd/user/display-daemon.service` | systemd user service |
| `/etc/sudoers.d/liu-display` | NOPASSWD rule for `chvt 1` and `chvt 2` only |
| `video` group membership | `sudo usermod -aG video liu` — required for `/dev/fb0` write access |
| `~/.config/display-state.json` | Persisted mode + settings |
| `/tmp/display-cover.jpg` | Downloaded cover art (ephemeral) |
| `/tmp/now-playing.png` | Current stable now-playing frame (ephemeral) |
| `/tmp/now-playing-new.png` | Freshly rendered frame before crossfade (ephemeral) |
| `/tmp/cf/frame-NN.png` | Crossfade intermediate frames (ephemeral, cleaned up after each transition) |
| `/tmp/cava-display.conf` | Generated cava config (ephemeral) |
| `/tmp/mpv-display.sock` | mpv IPC socket (ephemeral) |

---

## Dependencies

| Package | Install | Purpose |
|---------|---------|---------|
| `Pillow` | `uv pip install Pillow` → `~/.venv` | Image rendering, crossfade, visualizer frames |
| `yt-dlp` | `uv pip install yt-dlp` → `~/.venv` | YouTube search + stream URL extraction |
| `mpv` | `sudo apt install mpv` | DRM video/image display |
| `cava` | `sudo apt install cava` | Audio bar data from PipeWire |
| `playerctl` | already installed | MPRIS metadata + AVRCP playback control |

Cover art download uses `urllib.request` (stdlib).

---

## Constraints & Edge Cases

| Scenario | Handling |
|----------|----------|
| AVRCP artUrl empty or download fails | Black BG, text-only (or blank if overlay off) |
| DRM master held by orphaned mpv | Daemon kills orphan on startup |
| yt-dlp rate limit or network error | try/except, treat as not found, increment skip_count |
| yt-dlp returns multiple URL lines | Take only first non-empty line |
| Phone skips track while video plays | MetadataEvent → `stop` mpv → handle new track (skip_count unchanged) |
| 5 consecutive tracks without video | Revert to now-playing, status = no_videos_found |
| PipeWire combined sink changes mid-video | mpv silences; acceptable, matches system-wide behaviour |
| Daemon restart | Restore mode from JSON, idle screen, wait for MPRIS |
| `sudo chvt` from user service | NOPASSWD rule, no TTY/PAM needed |
| MPRIS event during crossfade | Queued, processed after crossfade loop completes |
| cava not installed | status = `"cava_unavailable"`; visualizer button greyed in UI |
| liu not in video group | `/dev/fb0` open fails; status = `"fb_permission_error"`; clear message in UI |
| /dev/fb0 pixel format (BGRA vs RGBA) | Detect bpp from sysfs; swap R/B channels in Pillow if needed |
| Framebuffer virtual_size ≠ display resolution | Use virtual_size for canvas; content is centred/cropped to fit |
| `playerctl next` after video — no metadata in 5s | Call `playerctl play` only (NOT a second next) to resume phone queue |

---

## Not In Scope

- Lyrics display
- Multiple simultaneous HDMI screens
- DLNA cover art (BT AVRCP only)
- 3D / OpenGL visualizers
- Visualizer colour theme customisation beyond mirror toggle (v1)
