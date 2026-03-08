"""Unit tests for workspace/tools/latency_tracker.py."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import workspace.tools.latency_tracker as lt


class TestComplexityAdjustedFloor(unittest.TestCase):
    """Test the complexity-adjusted latency floor formula."""

    def _adjusted_floor(self, prompt_chars: int) -> float:
        complexity_factor = min(1.0, max(0.25, prompt_chars / 2000.0))
        return lt.LATENCY_FLOOR_MS * complexity_factor

    def test_very_short_prompt_floor(self):
        # < 200 chars → factor clamped at 0.25
        floor = self._adjusted_floor(50)
        self.assertAlmostEqual(floor, lt.LATENCY_FLOOR_MS * 0.25, places=1)

    def test_exact_threshold_prompt(self):
        # 2000 chars → factor = 1.0 (full floor)
        floor = self._adjusted_floor(2000)
        self.assertAlmostEqual(floor, lt.LATENCY_FLOOR_MS, places=1)

    def test_long_prompt_capped(self):
        # > 2000 chars → factor still 1.0 (capped)
        floor = self._adjusted_floor(10000)
        self.assertAlmostEqual(floor, lt.LATENCY_FLOOR_MS, places=1)

    def test_medium_prompt_scales(self):
        # 1000 chars → factor = 0.5
        floor = self._adjusted_floor(1000)
        self.assertAlmostEqual(floor, lt.LATENCY_FLOOR_MS * 0.5, places=1)


class TestViolationDetection(unittest.TestCase):
    def _violation(self, latency_ms: float, prompt_chars: int) -> bool:
        complexity_factor = min(1.0, max(0.25, prompt_chars / 2000.0))
        adjusted_floor = lt.LATENCY_FLOOR_MS * complexity_factor
        return latency_ms < adjusted_floor and latency_ms > 0

    def test_zero_latency_not_violation(self):
        # Zero latency excluded (likely a non-event)
        self.assertFalse(self._violation(0, 100))

    def test_above_floor_not_violation(self):
        # Well above floor: no violation
        self.assertFalse(self._violation(5000, 2000))

    def test_below_floor_is_violation(self):
        # 1ms with full floor → violation
        self.assertTrue(self._violation(1, 2000))

    def test_short_prompt_higher_tolerance(self):
        # 25ms response to short prompt: below full floor (200ms) but above adjusted (50ms)
        self.assertFalse(self._violation(60, 50))  # 60ms > 200*0.25=50ms → no violation

    def test_short_prompt_very_fast_is_violation(self):
        # 10ms response to short prompt: below adjusted floor (50ms)
        self.assertTrue(self._violation(10, 50))


class TestRenderSummaryTable(unittest.TestCase):
    def test_empty_summary_renders(self):
        s = {"beings": {}, "total_calls": 0, "total_violations": 0}
        result = lt.render_summary_table(s)
        self.assertIn("Latency Tracker Summary", result)
        self.assertIn("Total calls: 0", result)
        self.assertIn("Total violations: 0", result)

    def test_being_data_appears(self):
        s = {
            "beings": {
                "Claude Code": {
                    "calls": 10,
                    "violations": 2,
                    "min_ms": 150.0,
                    "max_ms": 3200.0,
                    "mean_ms": 800.0,
                }
            },
            "total_calls": 10,
            "total_violations": 2,
        }
        result = lt.render_summary_table(s)
        self.assertIn("Claude Code", result)
        self.assertIn("10", result)
        self.assertIn("2", result)

    def test_multiple_beings_sorted(self):
        s = {
            "beings": {
                "Grok": {"calls": 3, "violations": 0, "min_ms": 100.0, "max_ms": 200.0, "mean_ms": 150.0},
                "Claude Code": {"calls": 10, "violations": 1, "min_ms": 50.0, "max_ms": 1000.0, "mean_ms": 500.0},
            },
            "total_calls": 13,
            "total_violations": 1,
        }
        result = lt.render_summary_table(s)
        # Claude Code (10 calls) should appear before Grok (3 calls) in output
        cc_pos = result.find("Claude Code")
        grok_pos = result.find("Grok")
        self.assertLess(cc_pos, grok_pos)


class TestRecordAndSummary(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._state_dir_orig = lt.STATE_DIR
        self._calls_orig = lt.CALLS_LOG
        self._summary_orig = lt.SUMMARY_FILE
        tmp = Path(self._tmpdir.name)
        lt.STATE_DIR = tmp
        lt.CALLS_LOG = tmp / "calls.jsonl"
        lt.SUMMARY_FILE = tmp / "summary.json"

    def tearDown(self):
        lt.STATE_DIR = self._state_dir_orig
        lt.CALLS_LOG = self._calls_orig
        lt.SUMMARY_FILE = self._summary_orig
        self._tmpdir.cleanup()

    def test_record_creates_files(self):
        lt.record_call("TestBeing", prompt_chars=500, latency_ms=1200.0)
        self.assertTrue(lt.CALLS_LOG.exists())
        self.assertTrue(lt.SUMMARY_FILE.exists())

    def test_record_increments_total(self):
        lt.record_call("TestBeing", prompt_chars=500, latency_ms=1200.0)
        lt.record_call("TestBeing", prompt_chars=500, latency_ms=800.0)
        s = lt._load_summary()
        self.assertEqual(s["total_calls"], 2)

    def test_violation_counted(self):
        # 10ms with 2000 chars → violation (below 200ms floor)
        lt.record_call("TestBeing", prompt_chars=2000, latency_ms=10.0)
        s = lt._load_summary()
        self.assertEqual(s["total_violations"], 1)

    def test_no_violation_for_long_latency(self):
        lt.record_call("TestBeing", prompt_chars=500, latency_ms=5000.0)
        s = lt._load_summary()
        self.assertEqual(s["total_violations"], 0)

    def test_summary_per_being(self):
        lt.record_call("Grok", prompt_chars=300, latency_ms=2000.0)
        lt.record_call("Claude Code", prompt_chars=400, latency_ms=1500.0)
        s = lt._load_summary()
        self.assertIn("Grok", s["beings"])
        self.assertIn("Claude Code", s["beings"])
        self.assertEqual(s["beings"]["Grok"]["calls"], 1)


if __name__ == "__main__":
    unittest.main()
