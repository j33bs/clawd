"""Tests for workspace/memory_ext/arousal_detector.py pure helper functions.

Covers (no file I/O):
- _sigmoid
- compute_arousal
- arousal_to_state
- modulate_response
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.arousal_detector import (  # noqa: E402
    _sigmoid,
    arousal_to_state,
    compute_arousal,
    modulate_response,
)


# ---------------------------------------------------------------------------
# _sigmoid
# ---------------------------------------------------------------------------

class TestSigmoid(unittest.TestCase):
    """Tests for _sigmoid() — logistic function clamped to (0,1)."""

    def test_zero_returns_half(self):
        self.assertAlmostEqual(_sigmoid(0.0), 0.5)

    def test_large_positive_approaches_1(self):
        self.assertGreater(_sigmoid(100.0), 0.99)

    def test_large_negative_approaches_0(self):
        self.assertLess(_sigmoid(-100.0), 0.01)

    def test_returns_float(self):
        self.assertIsInstance(_sigmoid(1.0), float)

    def test_positive_input_above_half(self):
        self.assertGreater(_sigmoid(1.0), 0.5)

    def test_negative_input_below_half(self):
        self.assertLess(_sigmoid(-1.0), 0.5)


# ---------------------------------------------------------------------------
# compute_arousal
# ---------------------------------------------------------------------------

class TestComputeArousal(unittest.TestCase):
    """Tests for compute_arousal() — weighted sigmoid of inputs."""

    def test_returns_float(self):
        result = compute_arousal(0, 1000, 0.0, 0.0)
        self.assertIsInstance(result, float)

    def test_result_in_unit_interval(self):
        for tc, lm, nv, sm in [(0, 1, 0.0, 0.0), (800, 100, 0.5, 0.5), (0, 1000000, -1.0, -1.0)]:
            val = compute_arousal(tc, lm, nv, sm)
            self.assertGreaterEqual(val, 0.0, f"negative for {tc,lm,nv,sm}")
            self.assertLessEqual(val, 1.0, f"above 1 for {tc,lm,nv,sm}")

    def test_high_tokens_high_arousal(self):
        low = compute_arousal(0, 1000, 0.0, 0.0)
        high = compute_arousal(10000, 100, 1.0, 1.0)
        self.assertGreater(high, low)

    def test_negative_token_count_treated_as_zero(self):
        result = compute_arousal(-999, 100, 0.0, 0.0)
        self.assertGreaterEqual(result, 0.0)

    def test_novelty_clamped_to_1(self):
        """Values beyond ±1 are clamped — should not raise."""
        result = compute_arousal(100, 100, 999.0, 0.0)
        self.assertLessEqual(result, 1.0)


# ---------------------------------------------------------------------------
# arousal_to_state
# ---------------------------------------------------------------------------

class TestArousalToState(unittest.TestCase):
    """Tests for arousal_to_state() — float → state string."""

    def test_below_0_3_is_idle(self):
        self.assertEqual(arousal_to_state(0.1), "IDLE")

    def test_0_3_boundary_is_active(self):
        self.assertEqual(arousal_to_state(0.3), "ACTIVE")

    def test_midrange_active(self):
        self.assertEqual(arousal_to_state(0.5), "ACTIVE")

    def test_0_6_boundary_is_engaged(self):
        self.assertEqual(arousal_to_state(0.6), "ENGAGED")

    def test_high_engaged(self):
        self.assertEqual(arousal_to_state(0.75), "ENGAGED")

    def test_0_8_boundary_is_overload(self):
        self.assertEqual(arousal_to_state(0.8), "OVERLOAD")

    def test_max_is_overload(self):
        self.assertEqual(arousal_to_state(1.0), "OVERLOAD")

    def test_zero_is_idle(self):
        self.assertEqual(arousal_to_state(0.0), "IDLE")

    def test_returns_string(self):
        self.assertIsInstance(arousal_to_state(0.5), str)


# ---------------------------------------------------------------------------
# modulate_response
# ---------------------------------------------------------------------------

class TestModulateResponse(unittest.TestCase):
    """Tests for modulate_response() — clips/prefixes text by arousal state."""

    def test_overload_adds_caution_prefix(self):
        result = modulate_response(0.9, "some text")
        self.assertTrue(result.startswith("[CAUTION]"))

    def test_overload_clips_long_text(self):
        long_text = "x" * 300
        result = modulate_response(0.9, long_text)
        self.assertLessEqual(len(result), 200)  # [CAUTION] + 180 chars + " ..."

    def test_engaged_clips_at_260(self):
        long_text = "y" * 400
        result = modulate_response(0.75, long_text)
        self.assertLessEqual(len(result), 260)

    def test_idle_returns_full_text(self):
        text = "short response"
        result = modulate_response(0.1, text)
        self.assertEqual(result, text)

    def test_active_returns_full_text(self):
        text = "medium response here"
        result = modulate_response(0.5, text)
        self.assertEqual(result, text)

    def test_empty_text_overload(self):
        result = modulate_response(0.9, "")
        self.assertIsInstance(result, str)

    def test_none_text_safe(self):
        result = modulate_response(0.1, None)
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        self.assertIsInstance(modulate_response(0.5, "test"), str)


if __name__ == "__main__":
    unittest.main()
