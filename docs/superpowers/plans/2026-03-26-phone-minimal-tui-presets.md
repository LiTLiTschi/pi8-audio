# Phone minimal UI, scene presets, and simple audio profile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a **`simple`** audio profile (BT → HDMI without `combine-stream`), **scene presets** (display + audio bundle) in a dedicated JSON file managed by a **TUI**, and a **minimal phone page** at **`/m`** that only switches display mode or activates scenes.

**Architecture:** Extract validation/IO into **`bin/pi8_presets.py`** (scene store: `~/.config/pi8-presets.json`). Extend **`apply_state`** in `audio-sync-web` for **`audio_profile`** `simple` \| `multi`. Add **`POST /display-mode`**, **`POST /scene/apply`**, **`GET /scenes`** (or reuse `GET` with path under `/m/api/…`) plus **`GET /m`** HTML. **Do not remove** existing **`/remote`** or embedded **`presets`** in `~/.config/audio-sync.json` (those are audio-only snapshots, `PRESET_KEYS` in `get_presets`); phone minimal UI lists **only scenes** from the new file. **TUI** uses stdlib **`curses`** and calls localhost HTTP for apply (reuse server logic) **or** imports `pi8_presets` + duplicates thin wrapper — **prefer HTTP** `POST http://127.0.0.1:8083/scene/apply` so one code path.

**Tech Stack:** Python 3, curses, PipeWire (`pactl`), existing `display-daemon` `:8084/set`.

**Spec:** `docs/superpowers/specs/2026-03-26-phone-minimal-tui-presets-design.md`

**Existing code to respect:**
- `bin/audio-sync-web`: `PRESET_KEYS`, `get_presets` / `save_preset` / `load_preset` / `delete_preset` (`~/.config/audio-sync.json` nested `presets`) — **unchanged behavior** for full UI.
- `GET /remote` — full phone remote (transport, volume, etc.); **`/m`** is **more** minimal per spec.

---

## File map

| File | Responsibility |
|------|----------------|
| `bin/pi8_presets.py` | **New.** `PRESETS_JSON`, `validate_scene_store`, `list_scenes`, `load_store`, `save_store`, `get_scene(name)`. |
| `bin/audio-sync-web` | `audio_profile` + `apply_state` branch; new routes; `GET /m`; import `pi8_presets` via `sys.path` from `Path(__file__).parent`. |
| `bin/pi8-audio-tui` | **New.** Curses: status, scene CRUD (edit via temp file + `$EDITOR` optional), reorder, `curl`/urllib apply. |
| `tests/test_pi8_presets.py` | **New.** `unittest` validation tests. |
| `deploy.sh` | Deploy `pi8_presets.py`, `pi8-audio-tui`. |
| `README.md` | Document `/m`, scenes vs legacy presets, TUI, `audio_profile`. |

### Scene file schema (`~/.config/pi8-presets.json`)

```json
{
  "version": 1,
  "presets": [
    {
      "name": "tv-bt-hdmi",
      "label": "TV",
      "display": { "mode": "now-playing" },
      "audio": {
        "profile": "simple",
        "hdmi_port": 0,
        "hdmi_enabled": true,
        "outputs_front_rear": false
      }
    }
  ]
}
```

`audio` merges into `load_state()` before `save_state` + `apply_state` (only keys whitelisted: `profile`, `hdmi_port`, `hdmi_enabled`, `outputs_front_rear`, optionally `source` if valid). Map `audio.profile` → state key **`audio_profile`**.

---

### Task 1: `bin/pi8_presets.py` + tests

**Files:**
- Create: `bin/pi8_presets.py`
- Create: `tests/test_pi8_presets.py`

- [ ] **Step 1:** Add failing `unittest` cases: empty store OK; invalid `version`; duplicate `name`; invalid `display.mode`; invalid `audio.profile`.

- [ ] **Step 2:** Run `python3 -m unittest tests.test_pi8_presets -v` — expect FAIL.

- [ ] **Step 3:** Implement validation + `ALLOWED_DISPLAY_MODES` (sync with `display-daemon`: at minimum `off`, `now-playing`, `visualizer`, `music-video` — grep `_state` / `setup(mode)` in `display-daemon` for full set).

- [ ] **Step 4:** Tests PASS; commit `feat: pi8_presets scene store validation`.

---

### Task 2: `audio_profile` + simple `apply_state` path

**Files:**
- Modify: `bin/audio-sync-web` — `load_state` default, `apply_state`, `PRESET_KEYS` (add `audio_profile` if scenes should round-trip into legacy presets — **optional**; can omit from PRESET_KEYS until needed)

- [ ] **Step 1:** Default `audio_profile: "multi"` when key missing.

- [ ] **Step 2:** Implement **`clear_combined_config()`**: write `context.modules = []\`n` to `COMBINED_CONF` **or** delete file; confirm PipeWire 1.x accepts empty `context.modules`.

- [ ] **Step 3:** In **`apply_state`**, when `audio_profile == "simple"`:
  - If `delay_ms` and `target` imply active delay filter, either force-clear delay for simple or document “simple ignores delay” — **spec:** clear `DELAY_CONF` when entering simple if delay is 0; if non-zero delay, return 400 from API or log warning and strip delay (pick one; recommend **strip delay** for simple with log line).
  - Call `clear_combined_config()` instead of `write_combined`.
  - After PipeWire restart + sleep, **`pactl set-default-sink <hdmi_logical_name>`** using `detect_hdmi_sinks()` + `state.get("hdmi_port",0)`; if `hdmi_enabled` false, set default to first available HDMI anyway for TV path (product decision: **simple implies HDMI default** — force `hdmi` as default sink always).

- [ ] **Step 4:** When **`multi`**, preserve current `write_combined` / `write_delay` logic.

- [ ] **Step 5:** Manual check: `systemctl --user restart pipewire`; `pactl info`; journal — no `combine-stream` in simple.

- [ ] **Step 6:** Commit `feat(audio): audio_profile simple|multi in apply_state`.

---

### Task 3: Scene HTTP API + apply pipeline

**Files:**
- Modify: `bin/audio-sync-web` — `do_GET` / `do_POST` whitelist

- [ ] **Step 1:** **`GET /scenes`** → `{ "ok": true, "scenes": [ {"name", "label"}, ... ] }` from `pi8_presets.load_store`.

- [ ] **Step 2:** **`POST /scene/apply`** body `{"name":"tv-bt-hdmi"}` with `_apply_lock`: load scene, validate, **merge `audio` into state**, `save_state`, **`apply_state(state)`**, then **`urllib` POST** `display` keys to `http://localhost:8084/set` (full `display` sub-object from scene, not only mode).

- [ ] **Step 3:** **`POST /display-mode`** body `{"mode":"off"}` — allowlist mode; forward minimal JSON to `8084/set`. Reject if mode unknown.

- [ ] **Step 4:** `curl` tests from Pi.

- [ ] **Step 5:** Commit `feat(web): /scenes /scene/apply /display-mode`.

---

### Task 4: `GET /m` minimal phone page

**Files:**
- Modify: `bin/audio-sync-web` — constant `MINIMAL_MOBILE_HTML`, ETag, route `GET /m`

- [ ] **Step 1:** Single-column UI: display mode buttons (fetch `GET /display-state` for current highlight); scene chips from `GET /scenes`; calls `POST /display-mode` / `POST /scene/apply`. **No** volume slider, **no** transport (spec: phone only display + scenes — if user wants transport, they use `/remote`).

- [ ] **Step 2:** Link footnote: “Advanced / remote” → `/remote` optional.

- [ ] **Step 3:** Manual phone test.

- [ ] **Step 4:** Commit `feat(web): /m minimal phone UI`.

---

### Task 5: `bin/pi8-audio-tui` (curses)

**Files:**
- Create: `bin/pi8-audio-tui`
- Modify: `deploy.sh`

- [ ] **Step 1:** `sys.path.insert(0, dirname)` import `pi8_presets`; main loop: Status | Scenes | Audio profile.

- [ ] **Step 2:** Scenes: `n` new (prompt name/label JSON or spawn editor), `d` delete, move up/down reorder list in JSON, `a` apply via `urllib.request.urlopen('http://127.0.0.1:8083/scene/apply', ...)`.

- [ ] **Step 3:** Audio profile: toggle `audio_profile` in `load_state`/`save_state` — **needs helper**: either `POST` new internal route `POST /audio-profile` or subprocess `python3 -c` importing a module; **add `POST /audio-profile`** `{"profile":"simple|multi"}` with `_apply_lock` to avoid brittle `-c` hacks.

- [ ] **Step 4:** Commit `feat: pi8-audio-tui` + `deploy.sh` + `POST /audio-profile`.

---

### Task 6: Docs + `pi8-audioctl` (optional)

- [ ] **Step 1:** README: scenes vs legacy presets, `/m`, TUI command.

- [ ] **Step 2:** Optional: `pi8-audioctl scene-list` / `scene-apply NAME`.

- [ ] **Step 3:** Commit `docs: minimal phone + scenes`.

---

## Verification checklist (end)

- [ ] `/m` on phone: change display mode; activate scene; no combine-stream in journal after simple scene.
- [ ] TUI: create scene, appears on `/m` after refresh.
- [ ] Legacy `/presets/load` still works for audio-only embedded presets.

---

## Execution handoff

**Plan complete:** `docs/superpowers/plans/2026-03-26-phone-minimal-tui-presets.md`

**Options:**
1. **Subagent-driven** — fresh subagent per task (`subagent-driven-development` skill).
2. **Inline** — execute in this session with checkpoints (`executing-plans` skill).

Which approach do you want?
