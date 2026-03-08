"""Tests for workspace/tacti/arousal_oscillator.py pure helpers.

Covers (no file I/O, no ZoneInfo required):
- ArousalOscillator._baseline_curve (static)
- ArousalOscillator._parse_time_from_line
- ArousalOscillator.explain (with empty memory dir)
"""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from tacti.arousal_oscillator import ArousalOscillator  # noqa: E402


# ---------------------------------------------------------------------------
# _baseline_curve (static method)
# ---------------------------------------------------------------------------

class TestBaselineCurve(unittest.TestCase):
    """Tests for ArousalOscillator._baseline_curve() — circadian Gaussian peaks."""

    def test_returns_float(self):
        self.assertIsInstance(ArousalOscillator._baseline_curve(10), float)

    def test_in_unit_interval(self):
        for h in range(24):
            val = ArousalOscillator._baseline_curve(h)
            self.assertGreaterEqual(val, 0.0, f"hour={h}")
            self.assertLessEqual(val, 1.0, f"hour={h}")

    def test_peak_near_hour_10(self):
        val_10 = ArousalOscillator._baseline_curve(10)
        val_3 = ArousalOscillator._baseline_curve(3)
        self.assertGreater(val_10, val_3)

    def test_peak_near_hour_15(self):
        val_15 = ArousalOscillator._baseline_curve(15)
        val_20 = ArousalOscillator._baseline_curve(20)
        self.assertGreater(val_15, val_20)

    def test_minimum_is_positive(self):
        # baseline = 0.20 + gaussian; always > 0
        for h in range(24):
            self.assertGreater(ArousalOscillator._baseline_curve(h), 0.0)

    def test_hour_10_above_floor(self):
        # Peak at 10 should exceed baseline floor (0.20)
        self.assertGreater(ArousalOscillator._baseline_curve(10), 0.20)

    def test_deterministic(self):
        self.assertAlmostEqual(
            ArousalOscillator._baseline_curve(12),
            ArousalOscillator._baseline_curve(12),
        )


# ---------------------------------------------------------------------------
# _parse_time_from_line
# ---------------------------------------------------------------------------

class TestParseTimeFromLine(unittest.TestCase):
    """Tests for ArousalOscillator._parse_time_from_line()."""

    def setUp(self):
        with tempfile.TemporaryDirectory() as td:
            # Instantiate with empty memory dir so no disk reads in _learned_bins
            self._osc = ArousalOscillator(repo_root=td)
        self._tz = timezone.utc

    def test_hh_mm_time_parsed(self):
        file_date = datetime(2026, 3, 8, tzinfo=timezone.utc)
        dts = self._osc._parse_time_from_line("logged at 14:30", file_date, timezone.utc)
        self.assertEqual(len(dts), 1)
        self.assertEqual(dts[0].hour, 14)
        self.assertEqual(dts[0].minute, 30)

    def test_hh_mm_ss_time_parsed(self):
        file_date = datetime(2026, 3, 8, tzinfo=timezone.utc)
        dts = self._osc._parse_time_from_line("at 09:15:45", file_date, timezone.utc)
        self.assertGreaterEqual(len(dts), 1)
        self.assertEqual(dts[0].hour, 9)
        self.assertEqual(dts[0].minute, 15)

    def test_iso_timestamp_parsed(self):
        dts = self._osc._parse_time_from_line(
            "event 2026-03-08T10:30:00Z", None, timezone.utc
        )
        self.assertEqual(len(dts), 1)
        self.assertEqual(dts[0].hour, 10)

    def test_no_time_returns_empty(self):
        dts = self._osc._parse_time_from_line("no timestamps here", None, timezone.utc)
        self.assertEqual(dts, [])

    def test_returns_list(self):
        result = self._osc._parse_time_from_line("14:00", None, timezone.utc)
        self.assertIsInstance(result, list)

    def test_no_file_date_skips_hh_mm(self):
        # hh:mm patterns require file_date to reconstruct a full datetime
        dts = self._osc._parse_time_from_line("logged at 14:30", None, timezone.utc)
        # Without file_date, hh:mm patterns cannot produce a datetime
        self.assertEqual(len(dts), 0)


# ---------------------------------------------------------------------------
# explain (with empty repo / no memory files)
# ---------------------------------------------------------------------------

class TestExplainEmpty(unittest.TestCase):
    """Tests for ArousalOscillator.explain() — no memory files → baseline curve."""

    def test_explain_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            osc = ArousalOscillator(repo_root=td)
            result = osc.explain(datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc))
            self.assertIsInstance(result, dict)

    def test_required_keys_present(self):
        with tempfile.TemporaryDirectory() as td:
            osc = ArousalOscillator(repo_root=td)
            result = osc.explain(datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc))
            for key in ("baseline", "learned", "multiplier", "bins_used"):
                self.assertIn(key, result)

    def test_multiplier_in_unit_interval(self):
        with tempfile.TemporaryDirectory() as td:
            osc = ArousalOscillator(repo_root=td)
            result = osc.explain(datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc))
            self.assertGreaterEqual(result["multiplier"], 0.0)
            self.assertLessEqual(result["multiplier"], 1.0)

    def test_bins_used_zero_when_no_files(self):
        with tempfile.TemporaryDirectory() as td:
            osc = ArousalOscillator(repo_root=td)
            result = osc.explain(datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc))
            self.assertEqual(result["bins_used"], 0)

    def test_multiplier_method_returns_float(self):
        with tempfile.TemporaryDirectory() as td:
            osc = ArousalOscillator(repo_root=td)
            val = osc.multiplier(datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc))
            self.assertIsInstance(val, float)


if __name__ == "__main__":
    unittest.main()
