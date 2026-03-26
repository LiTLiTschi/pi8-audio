"""
HTTP client for audio-sync-web JSON endpoints (stdlib urllib).

Route inventory (from bin/audio-sync-web do_GET / do_POST handlers; grep self.path):

GET paths
---------
| Path / pattern              | Planned helper              |
|-----------------------------|-----------------------------|
| /state                      | get_state                   |
| /volume                     | get_volume                  |
| /player-status              | get_player_status           |
| /network-status             | get_network_status          |
| /presets                    | get_presets                 |
| /scenes                     | get_scenes                  |
| /m                          | get_minimal_mobile_page     |
| /remote                     | get_remote_page             |
| /debug                      | get_debug_page              |
| /display-log-ui             | get_display_log_ui_page     |
| /apply-status               | get_apply_status            |
| /display-state              | get_display_state           |
| /display-history            | get_display_history         |
| /sleep-timer                | get_sleep_timer             |
| /display-frame              | get_display_frame_png       |
| /display-log                | get_display_log             |
| /log/* (prefix)             | get_service_log             |
| (else)                      | get_main_page_html          |

POST paths
----------
| Path              | Planned helper        |
|-------------------|-----------------------|
| /simulate         | post_simulate         |
| /display-mode     | post_display_mode     |
| /scene/apply      | post_scene_apply      |
| /audio-profile    | post_audio_profile    |
| /balance          | post_balance          |
| /mode             | post_mode             |
| /source           | post_source           |
| /network-config   | post_network_config   |
| /buffers          | post_buffers          |
| /restart-service  | post_restart_service  |
| /play-sync-test   | post_play_sync_test   |
| /calib-stream     | post_calib_stream     |
| /presets          | post_presets          |
| /presets/load     | post_presets_load     |
| /presets/delete   | post_presets_delete   |
| /presets/schedule | post_presets_schedule |
| /hdmi             | post_hdmi             |
| /power            | post_power            |
| /display          | post_display          |
| /volume           | post_volume           |
| /player           | post_player           |
| /sleep-timer      | post_sleep_timer      |
| /debug-volume     | post_debug_volume     |
| /debug-test       | post_debug_test       |
| /apply            | post_apply_delay      |
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping


def _base_url() -> str:
    return os.environ.get("PI8_AUDIO_SYNC_URL", "http://127.0.0.1:8083").rstrip("/")


class Pi8AudioHttpError(Exception):
    """Non-2xx response from audio-sync-web (often JSON `{"ok": false, ...}`)."""

    def __init__(
        self,
        status: int,
        *,
        body: dict[str, Any] | None = None,
        raw: str | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.raw = raw
        super().__init__(status, body, raw)

    def __str__(self) -> str:  # pragma: no cover - exercised via repr in callers
        if self.body is not None:
            return f"Pi8AudioHttpError({self.status}, body={self.body!r})"
        return f"Pi8AudioHttpError({self.status}, raw={self.raw!r})"


def _parse_error_payload(raw: bytes) -> tuple[dict[str, Any] | None, str | None]:
    if not raw:
        return None, None
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, text
    if isinstance(data, dict):
        return data, None
    return None, text


def _request(method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
    base = _base_url()
    if not path.startswith("/"):
        path = "/" + path
    url = base + path
    data_bytes: bytes | None = None
    headers: dict[str, str] = {}
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_raw = e.read()
        d, r = _parse_error_payload(err_raw)
        raise Pi8AudioHttpError(e.code, body=d, raw=r) from e


def get_state() -> dict[str, Any]:
    return _request("GET", "/state")


def get_display_state() -> dict[str, Any]:
    """GET /display-state — display-daemon / overlay snapshot from audio-sync-web."""
    return _request("GET", "/display-state")


def post_mode(mode: str) -> Any:
    return _request("POST", "/mode", {"mode": mode})


def post_hdmi(enabled: bool, port: int = 0, outputs_front_rear: bool = True) -> Any:
    return _request(
        "POST",
        "/hdmi",
        {
            "enabled": enabled,
            "port": port,
            "outputs_front_rear": outputs_front_rear,
        },
    )


def post_apply_delay(target: str | None, delay_ms: float) -> dict[str, Any]:
    """POST /apply with the same JSON shape as the web UI: `target` and `delay_ms`."""
    return _request(
        "POST",
        "/apply",
        {"target": target, "delay_ms": delay_ms},
    )
