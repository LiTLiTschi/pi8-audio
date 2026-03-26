"""Tests for bin/pi8_presets.py (stdlib unittest)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import pi8_presets  # noqa: E402


class TestSceneValidation(unittest.TestCase):
    def test_default_store_ok(self):
        self.assertIsNone(pi8_presets.validate_scene_store(pi8_presets.default_store()))

    def test_valid_one_preset(self):
        data = {
            "version": 1,
            "presets": [
                {
                    "name": "tv",
                    "label": "TV",
                    "display": {"mode": "off"},
                    "audio": {"profile": "simple", "hdmi_port": 0},
                }
            ],
        }
        self.assertIsNone(pi8_presets.validate_scene_store(data))

    def test_rejects_bad_version(self):
        err = pi8_presets.validate_scene_store({"version": 2, "presets": []})
        self.assertIsNotNone(err)

    def test_rejects_duplicate_names(self):
        err = pi8_presets.validate_scene_store(
            {
                "version": 1,
                "presets": [
                    {"name": "x", "display": {"mode": "off"}, "audio": {"profile": "multi"}},
                    {"name": "x", "display": {"mode": "off"}, "audio": {"profile": "multi"}},
                ],
            }
        )
        self.assertIsNotNone(err)

    def test_rejects_bad_display_mode(self):
        err = pi8_presets.validate_scene_store(
            {
                "version": 1,
                "presets": [
                    {"name": "a", "display": {"mode": "cinema"}, "audio": {"profile": "simple"}},
                ],
            }
        )
        self.assertIsNotNone(err)

    def test_rejects_bad_audio_profile(self):
        err = pi8_presets.validate_scene_store(
            {
                "version": 1,
                "presets": [
                    {"name": "a", "display": {"mode": "off"}, "audio": {"profile": "wat"}},
                ],
            }
        )
        self.assertIsNotNone(err)

    def test_list_scene_summaries(self):
        data = {
            "version": 1,
            "presets": [
                {"name": "a", "label": "A", "display": {"mode": "off"}, "audio": {"profile": "simple"}},
                {"name": "b", "display": {"mode": "visualizer"}, "audio": {"profile": "multi"}},
            ],
        }
        s = pi8_presets.list_scene_summaries(data)
        self.assertEqual(len(s), 2)
        self.assertEqual(s[0]["name"], "a")
        self.assertEqual(s[0]["label"], "A")
        self.assertEqual(s[1]["label"], "b")

    def test_merge_audio_into_state(self):
        st = {"balance": 0, "hdmi_enabled": False}
        p = {
            "audio": {
                "profile": "simple",
                "hdmi_port": 1,
                "hdmi_enabled": True,
                "outputs_front_rear": False,
                "source": "bluetooth",
            }
        }
        m = pi8_presets.merge_audio_into_state(p, st)
        self.assertEqual(m["audio_profile"], "simple")
        self.assertEqual(m["hdmi_port"], 1)
        self.assertTrue(m["hdmi_enabled"])
        self.assertFalse(m["outputs_front_rear"])
        self.assertEqual(m["source"], "bluetooth")
        self.assertEqual(m["balance"], 0)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "pi8-presets.json")
            data = {
                "version": 1,
                "presets": [
                    {
                        "name": "one",
                        "display": {"mode": "music-video"},
                        "audio": {"profile": "multi"},
                    }
                ],
            }
            pi8_presets.save_store(data, path=path)
            loaded = pi8_presets.load_store(path=path)
            self.assertEqual(loaded, data)

    def test_get_scene(self):
        data = {
            "version": 1,
            "presets": [
                {"name": "x", "display": {"mode": "off"}, "audio": {"profile": "simple"}},
            ],
        }
        g = pi8_presets.get_scene("x", data)
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["name"], "x")


if __name__ == "__main__":
    unittest.main()
