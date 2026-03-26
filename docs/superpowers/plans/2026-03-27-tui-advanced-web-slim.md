# Full advanced TUI + slim desktop Web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move essentially all **power-user / calibration / multi-output** controls from the clogged `audio-sync-web` main page into a **capable local TUI**, then **strip** the primary HTML to a small **launcher + live status** while keeping **`/m`** (phone), **`/remote`**, **`/debug`**, **`/display-log-ui`**, and all existing **JSON POST/GET** routes working unchanged.

**Architecture:** Keep **`audio-sync-web`** as the single HTTP control plane (no new daemon). Add a thin **`pi8_audio_http.py`** (or extend **`pi8-audioctl`**) module that wraps existing endpoints with small functions the TUI calls via **`urllib`** (same contracts as the browser). Replace the minimal **`bin/pi8-audio-tui`** with either a **multi-screen `curses`** app (stdlib only) or a **`textual`** app (optional `pip install textual`; better forms). **Slim `HTML`**: remove large `<details>` blocks and tab panes; replace with compact links + 2–3 live status fetches (`/state`, `/display-state`, `/apply-status`) and explicit text: *“Advanced tuning: run `audio` on the Pi (TUI).”*

**Tech Stack:** Python 3.12, existing `audio-sync-web` routes, `display-daemon` `:8084`, optional **Textual**, **`unittest`** for the HTTP client module (mock `urllib`).

**Spec / product intent:** @ `docs/superpowers/specs/2026-03-26-phone-minimal-tui-presets-design.md` (phone stays minimal; advanced lives on the Pi).

---

## File map (creates / modifies)

| File | Responsibility |
|------|----------------|
| `bin/pi8_audio_http.py` | **New.** Typed wrappers: `get_state()`, `post_apply()`, `post_mode`, `post_source`, `post_hdmi`, `post_buffers`, `post_balance`, `post_volume`, `post_display`, `post_calib_stream`, `post_restart_service`, `get_display_state`, `post_network_config`, legacy `/presets/*`, `/scene/apply`, `/audio-profile`, etc. Base URL from `PI8_AUDIO_SYNC_URL`. |
| `bin/pi8-audio-tui` | **Replace/expand.** Main menu → sub-screens that call `pi8_audio_http` + `pi8_presets` + `subprocess` for `pi8-audioctl` / `systemctl` where no HTTP exists. |
| `bin/audio-sync-web` | **Slim `HTML` constant** and related inline JS/CSS: delete or relocate bulky panels; keep **endpoints** intact; add short launcher copy + maybe `/favicon` unchanged. |
| `README.md` | TUI capabilities matrix; optional `textual` install; “desktop UI is intentionally thin.” |
| `tests/test_pi8_audio_http.py` | **New.** `unittest` + `unittest.mock.patch` for `urlopen` on 3–5 representative calls. |
| `deploy.sh` | Deploy `pi8_audio_http.py` beside other `~/bin` tools if split from TUI file. |

---

## Inventory — main Web UI (`HTML` in `audio-sync-web`) → TUI destination

Map every removed panel to a TUI screen (and existing HTTP path):

| Web section (approx. line area in `HTML`) | HTTP surface today | TUI screen |
|-------------------------------------------|-------------------|------------|
| Stereo / Surround (`switchMode`) | `POST /mode` | **Audio → routing → channel mode** |
| Outputs: front+rear, HDMI enable/port | `POST /hdmi` | **Audio → outputs** |
| Source: BT / local / USB / network | `POST /source` | **Audio → source** |
| Scream / network config | `POST /network-config`, status via `GET /network-status` | **Audio → network (Scream)** |
| Delay target + slider + apply/reset | `POST /apply` (see JS payload) | **Audio → sync delay** |
| Buffer front/rear | `POST /buffers` | **Audio → ALSA buffers** |
| Balance + master volume + mute | `POST /balance`, `POST /volume` | **Audio → levels** |
| Display modes + overlay + themes + sleep | `POST /display`, `GET /display-state`, sleep `POST /sleep-timer` | **Display** (subset: mirror today’s JS fields; complex video/cover-art keys may stay `$EDITOR` → `display-daemon` state file **or** full form in TUI POST `/display`) |
| Test / simulate metadata | `POST` simulate via proxy in handler | **Debug → simulate** (optional, low priority) |
| Video / cover-art `<details>` | `POST /display` with many keys | **Display → advanced JSON** (textual TextArea or spawn editor) |
| Legacy presets (audio-sync.json) | `GET/PST /presets*`, `/presets/load`, etc. | **Presets → legacy** |
| Scenes | already in TUI via `/scenes`, `/scene/apply` | **Presets → scenes** |
| Service restart grid (`svc-btn`) | `POST /restart-service`, `/power` | **System → services** |
| Bluetooth adapter (if in UI) | routes under `/bluetooth-adapter` | **System → Bluetooth** (HTTP or `pi8-audioctl bluetooth-adapter`) |
| Calibration stream | `POST /calib-stream` | **Tools → calibration** (confirm dialog) |
| Sync test tone | `POST /play-sync-test` | **Tools → sync test** |

**Non-HTTP / CLI-only today:** anything only in **`pi8-audioctl`** (e.g. `scene-list`, raw `journalctl`) — TUI shells out or later add thin HTTP wrappers (YAGNI unless needed).

---

### Task 1: Lock the HTTP client surface (`pi8_audio_http.py`)

**Files:**
- Create: `bin/pi8_audio_http.py`
- Create: `tests/test_pi8_audio_http.py`

- [ ] **Step 1:** Grep `bin/audio-sync-web` `do_POST` / `do_GET` for every `self.path ==` and build a **checklist table** in a comment at top of `pi8_audio_http.py` (path → helper name).

- [ ] **Step 2:** Write **failing tests** that mock `urllib.request.urlopen` and assert correct URL, method, JSON body for:
  - `post_mode("surround")`
  - `post_hdmi(True, port=1, outputs_front_rear=False)`
  - `get_state()`

- [ ] **Step 3:** Implement minimal `pi8_audio_http.py` with `_request(method, path, body=None)`, JSON encode/decode, raise `Pi8AudioHttpError` on non-2xx with parsed body.

- [ ] **Step 4:** Run `python3 -m unittest tests.test_pi8_audio_http -v` → PASS.

- [ ] **Step 5:** Commit `feat: pi8_audio_http client + tests`.

---

### Task 2: Expand `apply` payload helper (if JS builds it ad hoc)

**Files:**
- Read: `bin/audio-sync-web` embedded `<script>` for `#apply-btn` / `fetch('/apply'...`
- Modify: `bin/pi8_audio_http.py` — add `post_apply_state(...)` matching **exact** JSON keys the Web UI sends today.

- [ ] **Step 1:** Capture one real `POST /apply` body from browser devtools **or** trace JS → reproduce in a unit test fixture.

- [ ] **Step 2:** Implement `post_apply_state` and test round-trip shape (dict equality).

- [ ] **Step 3:** Commit `fix: mirror web apply JSON in client`.

---

### Task 3: TUI shell — menu + shared status bar

**Files:**
- Modify: `bin/pi8-audio-tui` (major)
- Depends on: `bin/pi8_audio_http.py`

- [ ] **Step 1:** Choose stack: **Textual** (recommended for >20 fields) vs **curses** (stdlib). If Textual: add optional `pip install textual` note in README; guard import with fallback message.

- [ ] **Step 2:** Main menu entries: **Dashboard | Audio | Display | Presets | System | Tools | Quit**.

- [ ] **Step 3:** Dashboard: `get_state()`, `wpctl status` snippet (`subprocess`), `get_display_state()`, last line of `journalctl --user -u pipewire -n 1` optional.

- [ ] **Step 4:** Manual run on Pi: `python3 ~/bin/pi8-audio-tui` navigates all menus without exception.

- [ ] **Step 5:** Commit `feat(tui): main shell + dashboard`.

---

### Task 4: TUI — Audio group screens

**Files:**
- Modify: `bin/pi8-audio-tui`

- [ ] **Step 1:** **Routing:** stereo/surround, outputs, hdmi, source — call `pi8_audio_http` (`/mode`, `/hdmi`, `/source`).

- [ ] **Step 2:** **Network:** edit fields + `POST /network-config`; show `GET /network-status`.

- [ ] **Step 3:** **Sync delay + buffers + balance + volume** — parity with Web sliders (numeric entry ok).

- [ ] **Step 4:** When `audio_profile=simple`, show warning before enabling delay/surround that behavior may be ignored (match `apply_state` rules).

- [ ] **Step 5:** Commit `feat(tui): audio tuning screens`.

---

### Task 5: TUI — Display + Presets + System + Tools

**Files:**
- Modify: `bin/pi8-audio-tui`

- [ ] **Step 1:** **Display:** minimal parity: mode, overlay, mirror, theme, sleep timer — `POST /display` with same JSON as current JS `applyDisplayOptions` / `applyDisplayMode`. *Advanced* video/cover-art: offer “Edit raw JSON” → temp file + `POST /display`.

- [ ] **Step 2:** **Presets:** integrate existing **scenes** (`pi8_presets`) + **legacy** audio presets (`/presets/load`, save, delete) in one submenu with clear labels.

- [ ] **Step 3:** **System:** service restart presets (PipeWire stack, bluetooth, ALL) mirroring `svc-btn` rules; **power** stop/start if still desired.

- [ ] **Step 4:** **Tools:** calibration stream + sync test with **confirm** prompt.

- [ ] **Step 5:** Commit `feat(tui): display, system, tools`.

---

### Task 6: Slim main `HTML` in `audio-sync-web`

**Files:**
- Modify: `bin/audio-sync-web` (`HTML` string + any dead JS/CSS)

- [ ] **Step 1:** Replace inner `.card` body with: title, paragraph, links **`/m`**, **`/remote`**, **`/debug`**, **`/display-log-ui`**, optional **`/log/web`**, and static text: run **`audio`** on the Pi for advanced tuning.

- [ ] **Step 2:** Add tiny **status** strip: `fetch('/state')` + `fetch('/display-state')` — 4–6 lines JSON pretty or key fields only.

- [ ] **Step 3:** Delete unused JS functions and CSS blocks (grep for orphan `function` / ids). Run `python3 -m py_compile bin/audio-sync-web`.

- [ ] **Step 4:** Manual browser check desktop + mobile width: no broken console errors for kept fetches.

- [ ] **Step 5:** Commit `refactor(web): slim main page; advanced in TUI`.

---

### Task 7: Docs + deploy + verification

**Files:**
- Modify: `README.md`, `deploy.sh` (if new `pi8_audio_http.py` must be copied)

- [ ] **Step 1:** README: **TUI** section with screen list; **Web** section clarifies `/` is launcher, **`/m`** is phone, **`/remote`** is transport/volume remote.

- [ ] **Step 2:** `deploy.sh` `cp` for `pi8_audio_http.py` to `~/bin/`.

- [ ] **Step 3:** Run `bash deploy.sh` on Pi; smoke: `audio` → change one setting → confirm `/state` via curl.

- [ ] **Step 4:** `python3 -m unittest discover -s tests -v`.

- [ ] **Step 5:** Commit `docs: TUI-first operations`.

---

## Verification (whole feature)

- [ ] All **old** `fetch` routes used by removed JS are either **unused** or **still referenced** intentionally from slim page.
- [ ] **`/m`** unchanged behavior for phone users.
- [ ] **`/remote`** unchanged.
- [ ] **No regression** on `POST /apply`, `/hdmi`, `/display`, `/restart-service` (TUI uses same bodies as Web did).
- [ ] **`simple` / `multi`** profile rules still documented when tuning from TUI.

---

## Optional: plan review (@ writing-plans)

- Dispatch **plan-document-reviewer** with: this file + spec `docs/superpowers/specs/2026-03-26-phone-minimal-tui-presets-design.md`. Fix loops ≤3.

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-03-27-tui-advanced-web-slim.md`

**Choose execution:**

1. **Subagent-driven (recommended)** — one subagent per task, review between tasks (`subagent-driven-development` skill).  
2. **Inline** — implement in this session with checkpoints (`executing-plans` skill).

Which approach do you want?
