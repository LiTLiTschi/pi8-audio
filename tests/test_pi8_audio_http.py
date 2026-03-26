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


if __name__ == "__main__":
    unittest.main()
