import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.arousal_detector import arousal_to_state, compute_arousal, get_arousal_state, modulate_response


class TestMemoryExtArousal(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(arousal_to_state(0.1), "IDLE")
        self.assertEqual(arousal_to_state(0.4), "ACTIVE")
        self.assertEqual(arousal_to_state(0.7), "ENGAGED")
        self.assertEqual(arousal_to_state(0.9), "OVERLOAD")

    def test_modulation(self):
        base = "x" * 300
        out = modulate_response(0.95, base)
        self.assertTrue(out.startswith("[CAUTION]"))
        self.assertLess(len(out), 220)

    def test_state_write_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "arousal_state.json"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                _ = get_arousal_state(10, 20, 0.1, 0.1)
                self.assertFalse(target.exists())
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                _ = get_arousal_state(10, 20, 0.1, 0.1)
                self.assertTrue(target.exists())


# ---------------------------------------------------------------------------
# compute_arousal — pure math, always [0, 1]
# ---------------------------------------------------------------------------

class TestComputeArousal(unittest.TestCase):
    """Tests for compute_arousal() — sigmoid over weighted inputs."""

    def test_returns_float(self):
        self.assertIsInstance(compute_arousal(0, 1000, 0.0, 0.0), float)

    def test_result_in_unit_interval(self):
        for tc, lat, nov, sent in [
            (0, 1, -1.0, -1.0),
            (0, 1000, 0.0, 0.0),
            (10000, 1, 1.0, 1.0),
            (800, 300, 0.5, 0.5),
        ]:
            val = compute_arousal(tc, lat, nov, sent)
            self.assertGreaterEqual(val, 0.0, msg=f"Below 0 for {tc},{lat},{nov},{sent}")
            self.assertLessEqual(val, 1.0, msg=f"Above 1 for {tc},{lat},{nov},{sent}")

    def test_negative_token_count_clamped(self):
        # max(0, token_count) — negative tokens treated as zero
        val_neg = compute_arousal(-999, 1000, 0.0, 0.0)
        val_zero = compute_arousal(0, 1000, 0.0, 0.0)
        self.assertAlmostEqual(val_neg, val_zero, places=10)

    def test_novelty_clamped_to_minus1(self):
        val_extreme = compute_arousal(0, 1000, -99.0, 0.0)
        val_clamped = compute_arousal(0, 1000, -1.0, 0.0)
        self.assertAlmostEqual(val_extreme, val_clamped, places=10)

    def test_sentiment_clamped_to_plus1(self):
        val_extreme = compute_arousal(0, 1000, 0.0, 99.0)
        val_clamped = compute_arousal(0, 1000, 0.0, 1.0)
        self.assertAlmostEqual(val_extreme, val_clamped, places=10)

    def test_high_tokens_increases_arousal(self):
        low = compute_arousal(0, 1000, 0.0, 0.0)
        high = compute_arousal(10000, 1000, 0.0, 0.0)
        self.assertGreater(high, low)

    def test_latency_1_vs_latency_large(self):
        # latency_term = 1/latency_ms; low latency → higher arousal
        fast = compute_arousal(0, 1, 0.0, 0.0)
        slow = compute_arousal(0, 100000, 0.0, 0.0)
        self.assertGreater(fast, slow)

    def test_deterministic(self):
        v1 = compute_arousal(400, 500, 0.3, 0.1)
        v2 = compute_arousal(400, 500, 0.3, 0.1)
        self.assertEqual(v1, v2)


# ---------------------------------------------------------------------------
# arousal_to_state — classification thresholds
# ---------------------------------------------------------------------------

class TestArousalToState(unittest.TestCase):
    """Tests for arousal_to_state() — level → label mapping."""

    def test_idle_below_03(self):
        self.assertEqual(arousal_to_state(0.0), "IDLE")
        self.assertEqual(arousal_to_state(0.29), "IDLE")

    def test_active_at_03(self):
        self.assertEqual(arousal_to_state(0.3), "ACTIVE")
        self.assertEqual(arousal_to_state(0.59), "ACTIVE")

    def test_engaged_at_06(self):
        self.assertEqual(arousal_to_state(0.6), "ENGAGED")
        self.assertEqual(arousal_to_state(0.79), "ENGAGED")

    def test_overload_at_08(self):
        self.assertEqual(arousal_to_state(0.8), "OVERLOAD")
        self.assertEqual(arousal_to_state(1.0), "OVERLOAD")

    def test_value_above_1_clamped(self):
        # max(0, min(1, ...)) clamps out-of-range input
        self.assertEqual(arousal_to_state(2.0), "OVERLOAD")

    def test_value_below_0_clamped(self):
        self.assertEqual(arousal_to_state(-1.0), "IDLE")

    def test_returns_string(self):
        self.assertIsInstance(arousal_to_state(0.5), str)


# ---------------------------------------------------------------------------
# modulate_response — string manipulation by arousal state
# ---------------------------------------------------------------------------

class TestModulateResponse(unittest.TestCase):
    """Tests for modulate_response() — text shaping based on state."""

    def test_overload_adds_caution_prefix(self):
        out = modulate_response(0.9, "Hello world")
        self.assertTrue(out.startswith("[CAUTION]"))

    def test_overload_clips_at_180_chars_of_text(self):
        base = "A" * 300
        out = modulate_response(0.9, base)
        # prefix "[CAUTION] " + 180 chars + possible " ..."
        self.assertIn("[CAUTION]", out)
        self.assertLess(len(out), 220)

    def test_overload_appends_ellipsis_when_clipped(self):
        base = "B" * 300
        out = modulate_response(0.9, base)
        self.assertTrue(out.endswith("...") or out.endswith("... ") or " ..." in out)

    def test_engaged_clips_at_260(self):
        base = "C" * 400
        out = modulate_response(0.7, base)
        self.assertLessEqual(len(out), 260)

    def test_engaged_short_text_not_clipped(self):
        base = "Short text"
        out = modulate_response(0.7, base)
        self.assertEqual(out, base)

    def test_idle_passthrough(self):
        base = "D" * 400
        out = modulate_response(0.1, base)
        self.assertEqual(out, base)

    def test_active_passthrough(self):
        base = "E" * 400
        out = modulate_response(0.45, base)
        self.assertEqual(out, base)

    def test_empty_string_overload(self):
        out = modulate_response(0.9, "")
        self.assertTrue(out.startswith("[CAUTION]"))


if __name__ == "__main__":
    unittest.main()
