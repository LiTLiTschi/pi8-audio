# Design: minimal phone surface + TUI + presets (2026-03-26)

## Goals

1. **Simple audio path** — A **“simple”** profile routes Bluetooth A2DP straight to the **native HDMI sink** (no `libpipewire-module-combine-stream` graph for that profile), avoiding combine/clock pain for the common BT → TV use case.
2. **Phone usage** — From the phone, users may **only**:
   - Change **display mode** (same coarse modes as today: `off`, `now-playing`, `visualizer`, `music-video`, etc.), and/or
   - **Activate a named preset** from a list defined on the Pi.
3. **No power-user controls on phone** — No sliders, delays, combine tuning, buffer tweaks, or Bluetooth adapter surgery on the mobile surface.
4. **TUI** — Local (SSH or console) **terminal UI** for stack status, **preset create / edit / delete / reorder**, optional **audio profile** (`simple` vs `multi`), logs, and any retained advanced actions.

## Non-goals (this phase)

- Replacing `display-daemon`’s localhost API semantics beyond what’s needed for preset application.
- Preset authoring on the phone.
- Removing `audio-sync-web` in one shot; it may shrink to proxy + advanced routes only, or coexist with a new control service (see Implementation options).

## Preset model

A **preset** is a **named bundle** of settings applied atomically when activated. Minimum viable fields:

| Field | Description |
|--------|-------------|
| `name` | Short stable id (slug) for API + display label. |
| `label` | Optional human title (default = `name`). |
| `display` | Sub-object mirroring what `display-daemon` needs: at least `mode`; optionally `overlay_enabled`, `visualizer_mirror`, and other keys already persisted in display state today. |
| `audio` | Sub-object for pi8-audio: at least `profile` (`simple` \| `multi`); optional keys that today live in `~/.config/audio-sync.json` (e.g. `hdmi_enabled`, `hdmi_port`, `outputs_front_rear`) **only when** they are safe to apply without interactive confirmation. |

**Ordering:** Presets have a `order` or array order in the store so the phone UI can show a consistent list.

**Storage:** e.g. `~/.config/pi8-presets.json` (versioned schema `"version": 1`). TUI edits this file; a **validation** step rejects incomplete presets before save.

**Application order when a preset is activated:** Apply **audio** first (if PipeWire restart is required), then **display** (so HDMI/mode is stable before `chvt` / mpv). Exact sequencing must match today’s `apply_state` + display `POST /set` ordering to avoid flicker or stale sinks.

## Phone API surface (coarse)

All routes remain behind the existing **LAN HTTP** entrypoint (today `audio-sync-web` on 8083), with **no new fine-grained tuning** endpoints exposed to the phone.

Suggested responsibilities:

1. **Display mode only** — `POST` with body `{ "mode": "<mode>" }` (or equivalent) that proxies to `display-daemon` only; rejects unknown modes.
2. **List presets** — `GET` returns ordered list: `{ "presets": [ { "name", "label" }, ... ] }`.
3. **Activate preset** — `POST` with `{ "preset": "<name>" }` loads preset from disk, validates, applies audio bundle then display bundle, returns `ok` / error message.

**Security note:** Keep or add **light authentication** if the service is exposed beyond trusted LAN (out of scope for v1; document “trusted network only” if unchanged).

## TUI (local)

- **View:** Service status (reuse patterns from `pi8-audioctl status`), default sink / profile, current display mode, last journal lines.
- **Presets:** List, create, edit (form or YAML-like editor), delete, reorder; **validate** before save.
- **Audio profile:** Switch `simple` / `multi` without a full preset (still useful for debugging).
- **Optional:** Jump to “open advanced in browser” URL for legacy `audio-sync-web` if it remains.

Implementation stack: prefer **stdlib + minimal deps** (e.g. `textual` if acceptable in `README` deps) to match the Pi environment; alternative is an extended **interactive `pi8-audioctl`** with `curses` for zero new packages.

## Audio: `simple` vs `multi`

- **`simple`:** Remove or bypass `~/.config/pipewire/pipewire.conf.d/combined.conf` generation for this profile; **default sink** = chosen HDMI ALSA/PipeWire sink (`wpctl` / `pactl`); no `combine.latency-compensate` path for routine playback.
- **`multi`:** Current behavior: generate `combined.conf` with combine-stream rules, front/rear/HDMI per existing `audio-sync-web` / state file.

Switching profiles may require **user** `systemctl --user restart pipewire pipewire-pulse wireplumber` (same as today’s `apply_state`).

## Relationship to existing components

| Component | Role after change |
|-----------|---------------------|
| `display-daemon` | Unchanged contract (`localhost:8084`); preset **display** section maps to its `/set` payload. |
| `audio-sync-web` | Option A: thin to **proxy + `/m` phone page** + advanced `/` for desktop; Option B: new small `pi8-control` service for phone routes, `audio-sync-web` optional for advanced only. |
| `pi8-audioctl` | Library of subprocess helpers TUI can import, or TUI wraps CLI. |
| `pi8-tty-dash` | Optional link from TUI; unchanged or shows current preset name. |

## Success criteria

- Phone user can switch display mode and pick presets **without** seeing combine/delay/USB options.
- Creating a preset on the Pi via TUI makes it appear on the phone list within one refresh.
- **`simple`** profile: no `mod.combine-stream` in the active graph for routine BT → HDMI playback (verify with `pw-cli` / journal absence of combine errors under normal use).
- **`multi`** profile: preserves today’s multi-output behavior for users who opt in via TUI or preset.

## Open decisions (implementation planning)

1. Single process vs split control service for phone routes.
2. TUI framework: `textual` vs stdlib `curses`.
3. Whether **display-only** quick toggles on the phone are redundant if every preset always sets `display.mode` (keep both: direct mode = fewer taps, presets = full scene).

---

**Status:** Approved direction from product discussion (2026-03-26). Next step: implementation plan (`writing-plans` skill) before code changes.
