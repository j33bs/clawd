import json
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer, _CIRCADIAN_BOUNDS


class TestCathedralCircadianAmbient(unittest.TestCase):
    def _renderer_stub(self) -> FishTankRenderer:
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._circadian_timezone = "Australia/Brisbane"
        renderer.circadian_bias = {}
        renderer.circadian_variation = {}
        renderer.circadian_phase = "deep_night"
        renderer.circadian_anchor_a = "deep_night"
        renderer.circadian_anchor_b = "pre_dawn"
        renderer.circadian_blend = 0.0
        renderer.local_time_minutes = 0.0
        renderer.local_time_bucket = "00:00-00:59"
        return renderer

    def test_circadian_interpolates_between_anchors(self):
        renderer = self._renderer_stub()
        bias = renderer._update_circadian_state(local_minutes=120.0, epoch_seconds=0.0)
        self.assertEqual(renderer.circadian_anchor_a, "deep_night")
        self.assertEqual(renderer.circadian_anchor_b, "pre_dawn")
        self.assertAlmostEqual(renderer.circadian_blend, 0.5, places=3)
        self.assertEqual(renderer.circadian_phase, "pre_dawn")
        self.assertAlmostEqual(bias["bg_indigo"], 0.98, places=2)
        self.assertEqual(renderer.local_time_bucket, "02:00-02:59")

    def test_circadian_variation_remains_bounded(self):
        renderer = self._renderer_stub()
        variation_limits = {
            "bloom_bias": 0.03,
            "circuit_gold": 0.02,
            "bg_blue": 0.02,
            "bg_amber": 0.015,
            "starfield": 0.025,
            "constellations": 0.02,
            "nebula_bias": 0.025,
        }
        for epoch in range(0, 3600 * 6, 397):
            bias = renderer._update_circadian_state(local_minutes=780.0, epoch_seconds=float(epoch))
            for key, (lo, hi) in _CIRCADIAN_BOUNDS.items():
                self.assertGreaterEqual(bias[key], lo, key)
                self.assertLessEqual(bias[key], hi, key)
            for key, limit in variation_limits.items():
                self.assertLessEqual(abs(float(renderer.circadian_variation.get(key, 0.0))), limit + 1e-6, key)

    def test_capture_state_exports_circadian_fields(self):
        with mock.patch.object(FishTankRenderer, "_init_gpu_backend"):
            renderer = FishTankRenderer(headless=True, require_gpu=False)
        renderer.update_signals({}, {})
        state = renderer.capture_state()
        for key in (
            "circadian_phase",
            "circadian_anchor_a",
            "circadian_anchor_b",
            "circadian_blend",
            "circadian_bias",
            "circadian_variation",
            "local_time_minutes",
            "local_time_bucket",
        ):
            self.assertIn(key, state)
        json.dumps(state)


if __name__ == "__main__":
    unittest.main()
