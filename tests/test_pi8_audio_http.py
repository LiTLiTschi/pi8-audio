"""Tests for bin/pi8_audio_http.py (stdlib unittest + mocked urllib)."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import pi8_audio_http  # noqa: E402


def _mock_http_response(payload: bytes, code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.getcode.return_value = code
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


class TestPi8AudioHttp(unittest.TestCase):
    def test_post_mode_surround(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://example:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "ok"}).encode()
                )
                out = pi8_audio_http.post_mode("surround")
                self.assertEqual(out["ok"], True)
                self.assertEqual(m.call_count, 1)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://example:8083/mode")
                self.assertEqual(req.method, "POST")
                hdrs = {k.lower(): v for k, v in req.header_items()}
                self.assertEqual(hdrs.get("content-type"), "application/json")
                body = json.loads(req.data.decode())
                self.assertEqual(body["mode"], "surround")

    def test_post_hdmi(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "Outputs"}).encode()
                )
                out = pi8_audio_http.post_hdmi(True, port=1, outputs_front_rear=False)
                self.assertEqual(out["ok"], True)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/hdmi")
                self.assertEqual(req.method, "POST")
                body = json.loads(req.data.decode())
                self.assertEqual(body["enabled"], True)
                self.assertEqual(body["port"], 1)
                self.assertEqual(body["outputs_front_rear"], False)

    def test_get_state(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                state = {"mode": "stereo", "source": "bluetooth"}
                m.return_value = _mock_http_response(json.dumps(state).encode())
                out = pi8_audio_http.get_state()
                self.assertEqual(out, state)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/state")
                self.assertEqual(req.method, "GET")
                self.assertIsNone(req.data)

    def test_get_display_state(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                payload = {"mode": "now-playing", "overlay": "minimal", "ok": True}
                m.return_value = _mock_http_response(json.dumps(payload).encode())
                out = pi8_audio_http.get_display_state()
                self.assertEqual(out, payload)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/display-state")
                self.assertEqual(req.method, "GET")
                self.assertIsNone(req.data)

    def test_post_apply_delay_front(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://example:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "applying": True}).encode()
                )
                out = pi8_audio_http.post_apply_delay("front", 12.5)
                self.assertEqual(out["ok"], True)
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/apply"))
                self.assertEqual(req.method, "POST")
                body = json.loads(req.data.decode())
                self.assertEqual(body["target"], "front")
                self.assertEqual(body["delay_ms"], 12.5)

    def test_post_apply_delay_none_target(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "applying": True}).encode()
                )
                pi8_audio_http.post_apply_delay(None, 0)
                req = m.call_args[0][0]
                raw = req.data.decode()
                self.assertIn('"target": null', raw)
                body = json.loads(raw)
                self.assertIsNone(body["target"])
                self.assertEqual(body["delay_ms"], 0)

    def test_post_source(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://example:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "ok"}).encode()
                )
                pi8_audio_http.post_source("network")
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://example:8083/source")
                self.assertEqual(req.method, "POST")
                self.assertEqual(json.loads(req.data.decode()), {"source": "network"})

    def test_post_network_config(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "saved", "config": {}}).encode()
                )
                pi8_audio_http.post_network_config(
                    group="239.1.1.1",
                    port=5000,
                    iface="eth0",
                    unicast=True,
                    rate=96000,
                    format="f32",
                )
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/network-config")
                body = json.loads(req.data.decode())
                self.assertEqual(
                    body,
                    {
                        "group": "239.1.1.1",
                        "port": 5000,
                        "iface": "eth0",
                        "unicast": True,
                        "rate": 96000,
                        "format": "f32",
                    },
                )

    def test_get_network_status(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                payload = {"running": True, "pid": 42, "config": {"port": 4010}}
                m.return_value = _mock_http_response(json.dumps(payload).encode())
                out = pi8_audio_http.get_network_status()
                self.assertEqual(out, payload)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/network-status")
                self.assertEqual(req.method, "GET")

    def test_post_buffers(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://example:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "Buffer"}).encode()
                )
                pi8_audio_http.post_buffers(1024, 512)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://example:8083/buffers")
                self.assertEqual(json.loads(req.data.decode()), {"front": 1024, "rear": 512})

    def test_post_balance(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "bal"}).encode()
                )
                pi8_audio_http.post_balance(-25)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/balance")
                self.assertEqual(json.loads(req.data.decode()), {"balance": -25})

    def test_post_volume_level_and_mute(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "volume": 33}).encode()
                )
                pi8_audio_http.post_volume(33, mute_toggle=False)
                req = m.call_args[0][0]
                self.assertEqual(
                    json.loads(req.data.decode()),
                    {"volume": 33, "mute_toggle": False},
                )

            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "volume": 33, "muted": True}).encode()
                )
                pi8_audio_http.post_volume(0, mute_toggle=True)
                req = m.call_args[0][0]
                self.assertEqual(
                    json.loads(req.data.decode()),
                    {"volume": 0, "mute_toggle": True},
                )

    def test_post_audio_profile(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://example:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "ok"}).encode()
                )
                pi8_audio_http.post_audio_profile("multi")
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://example:8083/audio-profile")
                self.assertEqual(json.loads(req.data.decode()), {"profile": "multi"})

    def test_get_apply_status(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                st = {"state": "idle", "error": None}
                m.return_value = _mock_http_response(json.dumps(st).encode())
                out = pi8_audio_http.get_apply_status()
                self.assertEqual(out, st)
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/apply-status"))
                self.assertEqual(req.method, "GET")

    def test_get_volume(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"volume": 77, "muted": False}).encode()
                )
                out = pi8_audio_http.get_volume()
                self.assertEqual(out["volume"], 77)
                req = m.call_args[0][0]
                self.assertEqual(req.get_full_url(), "http://127.0.0.1:8083/volume")
                self.assertEqual(req.method, "GET")

    def test_get_presets(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "presets": {"a": {}}}).encode()
                )
                out = pi8_audio_http.get_presets()
                self.assertIn("presets", out)
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/presets"))
                self.assertEqual(req.method, "GET")

    def test_get_scenes(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "scenes": []}).encode()
                )
                pi8_audio_http.get_scenes()
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/scenes"))
                self.assertEqual(req.method, "GET")

    def test_post_scene_apply(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True}).encode()
                )
                pi8_audio_http.post_scene_apply("tv-bt-hdmi")
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/scene/apply"))
                self.assertEqual(json.loads(req.data.decode()), {"name": "tv-bt-hdmi"})

    def test_post_display(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(json.dumps({"ok": True}).encode())
                pi8_audio_http.post_display(
                    {
                        "mode": "visualizer",
                        "overlay_enabled": True,
                        "visualizer_mirror": False,
                    }
                )
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/display"))
                body = json.loads(req.data.decode())
                self.assertEqual(body["mode"], "visualizer")
                self.assertTrue(body["overlay_enabled"])

    def test_post_sleep_timer_minutes(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "minutes": 45}).encode()
                )
                pi8_audio_http.post_sleep_timer_minutes(45)
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/sleep-timer"))
                self.assertEqual(json.loads(req.data.decode()), {"minutes": 45.0})

    def test_delete_sleep_timer(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True}).encode()
                )
                pi8_audio_http.delete_sleep_timer()
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/sleep-timer"))
                self.assertEqual(req.method, "DELETE")
                self.assertIsNone(req.data)

    def test_get_sleep_timer(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"active": False, "remaining_seconds": 0}).encode()
                )
                out = pi8_audio_http.get_sleep_timer()
                self.assertFalse(out["active"])
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/sleep-timer"))
                self.assertEqual(req.method, "GET")

    def test_post_restart_service(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "ok"}).encode()
                )
                pi8_audio_http.post_restart_service("DISPLAY_RESTART", scope="user")
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/restart-service"))
                self.assertEqual(
                    json.loads(req.data.decode()),
                    {"service": "DISPLAY_RESTART", "scope": "user"},
                )

    def test_post_power(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "stopped"}).encode()
                )
                pi8_audio_http.post_power("stop")
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/power"))
                self.assertEqual(json.loads(req.data.decode()), {"action": "stop"})

    def test_post_calib_stream(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "streaming": True}).encode()
                )
                pi8_audio_http.post_calib_stream(
                    "update", front_offset_ms=1.5, rear_offset_ms=0, volume=80
                )
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/calib-stream"))
                b = json.loads(req.data.decode())
                self.assertEqual(b["action"], "update")
                self.assertEqual(b["volume"], 80.0)

    def test_post_play_sync_test(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(json.dumps({"ok": True}).encode())
                pi8_audio_http.post_play_sync_test(0, 0)
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/play-sync-test"))
                self.assertEqual(
                    json.loads(req.data.decode()),
                    {"front_offset_ms": 0.0, "rear_offset_ms": 0.0},
                )

    def test_post_presets_save(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "presets": {}}).encode()
                )
                pi8_audio_http.post_presets_save("my-preset", snapshot_from_state=True)
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/presets"))
                self.assertEqual(json.loads(req.data.decode()), {"name": "my-preset"})

    def test_post_presets_load(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "msg": "loaded"}).encode()
                )
                pi8_audio_http.post_presets_load("x")
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/presets/load"))
                self.assertEqual(json.loads(req.data.decode()), {"name": "x"})

    def test_post_presets_delete(self):
        with patch.dict(os.environ, {"PI8_AUDIO_SYNC_URL": "http://127.0.0.1:8083"}):
            with patch("urllib.request.urlopen") as m:
                m.return_value = _mock_http_response(
                    json.dumps({"ok": True, "presets": {}}).encode()
                )
                pi8_audio_http.post_presets_delete("x")
                req = m.call_args[0][0]
                self.assertTrue(req.get_full_url().endswith("/presets/delete"))
                self.assertEqual(json.loads(req.data.decode()), {"name": "x"})


if __name__ == "__main__":
    unittest.main()
