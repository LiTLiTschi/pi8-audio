"""
Scene presets: display + audio bundles for pi8 (see docs/superpowers/specs/2026-03-26-*).
Used by audio-sync-web and pi8-audio-tui. Legacy audio-only presets live in audio-sync.json.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

PRESETS_PATH = os.path.expanduser("~/.config/pi8-presets.json")

ALLOWED_DISPLAY_MODES = frozenset({"off", "now-playing", "visualizer", "music-video"})
ALLOWED_AUDIO_PROFILES = frozenset({"simple", "multi"})
ALLOWED_AUDIO_SOURCES = frozenset({"bluetooth", "local", "usb", "network"})

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$", re.I)


def default_store() -> dict[str, Any]:
    return {"version": 1, "presets": []}


def validate_scene_store(data: dict[str, Any]) -> str | None:
    """Return error message, or None if OK."""
    if not isinstance(data, dict):
        return "root must be an object"
    ver = data.get("version")
    if ver != 1:
        return f"version must be 1, got {ver!r}"
    presets = data.get("presets")
    if not isinstance(presets, list):
        return "presets must be a list"
    seen: set[str] = set()
    for i, p in enumerate(presets):
        if not isinstance(p, dict):
            return f"presets[{i}] must be an object"
        name = p.get("name", "")
        if not isinstance(name, str) or not name.strip():
            return f"presets[{i}].name required"
        name = name.strip()
        if not _NAME_RE.match(name):
            return f"presets[{i}].name invalid (use letters, numbers, ._-)"
        if name in seen:
            return f"duplicate preset name: {name}"
        seen.add(name)
        label = p.get("label")
        if label is not None and not isinstance(label, str):
            return f"presets[{i}].label must be a string"
        disp = p.get("display")
        if not isinstance(disp, dict):
            return f"presets[{i}].display must be an object"
        mode = disp.get("mode")
        if mode not in ALLOWED_DISPLAY_MODES:
            return f"presets[{i}].display.mode invalid (got {mode!r})"
        audio = p.get("audio")
        if not isinstance(audio, dict):
            return f"presets[{i}].audio must be an object"
        prof = audio.get("profile")
        if prof not in ALLOWED_AUDIO_PROFILES:
            return f"presets[{i}].audio.profile must be simple|multi (got {prof!r})"
        if "hdmi_port" in audio:
            hp = audio["hdmi_port"]
            if hp not in (0, 1):
                return f"presets[{i}].audio.hdmi_port must be 0 or 1"
        if "hdmi_enabled" in audio and not isinstance(audio["hdmi_enabled"], bool):
            return f"presets[{i}].audio.hdmi_enabled must be bool"
        if "outputs_front_rear" in audio and not isinstance(audio["outputs_front_rear"], bool):
            return f"presets[{i}].audio.outputs_front_rear must be bool"
        if "source" in audio:
            if audio["source"] not in ALLOWED_AUDIO_SOURCES:
                return f"presets[{i}].audio.source invalid"
    return None


def load_store(path: str | None = None) -> dict[str, Any]:
    p = path or PRESETS_PATH
    if not os.path.isfile(p):
        return default_store()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default_store()
    if not isinstance(data, dict):
        return default_store()
    return data


def save_store(data: dict[str, Any], path: str | None = None) -> None:
    err = validate_scene_store(data)
    if err:
        raise ValueError(err)
    p = path or PRESETS_PATH
    os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, p)


def list_scene_summaries(store: dict[str, Any] | None = None) -> list[dict[str, str]]:
    data = store if store is not None else load_store()
    presets = data.get("presets", [])
    out = []
    if not isinstance(presets, list):
        return out
    for p in presets:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        label = p.get("label")
        if isinstance(label, str) and label.strip():
            out.append({"name": name, "label": label.strip()})
        else:
            out.append({"name": name, "label": name})
    return out


def get_scene(name: str, store: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = store if store is not None else load_store()
    presets = data.get("presets", [])
    if not isinstance(presets, list):
        return None
    for p in presets:
        if isinstance(p, dict) and str(p.get("name", "")).strip() == name:
            return p
    return None


def merge_audio_into_state(preset: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of state with audio fields from preset applied."""
    audio = preset.get("audio")
    if not isinstance(audio, dict):
        return state
    s = dict(state)
    prof = audio.get("profile")
    if prof in ALLOWED_AUDIO_PROFILES:
        s["audio_profile"] = prof
    if "hdmi_port" in audio:
        s["hdmi_port"] = int(audio["hdmi_port"])
    if "hdmi_enabled" in audio:
        s["hdmi_enabled"] = bool(audio["hdmi_enabled"])
    if "outputs_front_rear" in audio:
        s["outputs_front_rear"] = bool(audio["outputs_front_rear"])
    if "source" in audio and audio["source"] in ALLOWED_AUDIO_SOURCES:
        s["source"] = audio["source"]
    return s


def display_payload(preset: dict[str, Any]) -> dict[str, Any]:
    """display-daemon /set JSON from preset['display'] (extra keys are ignored server-side)."""
    disp = preset.get("display")
    if not isinstance(disp, dict):
        return {"mode": "off"}
    return dict(disp)
