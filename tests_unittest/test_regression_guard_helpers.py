"""Tests for pure helpers in tools/regression_guard.py.

within_tol() and LINE_RE are pure — no subprocess, no files.

Covers:
- within_tol() — tolerance check |val - base| <= tol
- LINE_RE regex — matches SIM headline output format
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RG_PATH = REPO_ROOT / "tools" / "regression_guard.py"

_spec = _ilu.spec_from_file_location("regression_guard_real", str(RG_PATH))
rg = _ilu.module_from_spec(_spec)
sys.modules["regression_guard_real"] = rg
_spec.loader.exec_module(rg)

within_tol = rg.within_tol
LINE_RE = rg.LINE_RE


# ---------------------------------------------------------------------------
# within_tol
# ---------------------------------------------------------------------------

class TestWithinTol(unittest.TestCase):
    """Tests for within_tol() — |val - base| <= tol."""

    def test_returns_bool(self):
        result = within_tol(1.0, 1.0, 0.1)
        self.assertIsInstance(result, bool)

    def test_exact_match(self):
        self.assertTrue(within_tol(5.0, 5.0, 0.0))

    def test_within_tolerance(self):
        self.assertTrue(within_tol(5.05, 5.0, 0.1))

    def test_exactly_at_tolerance(self):
        self.assertTrue(within_tol(5.1, 5.0, 0.1))

    def test_just_outside_tolerance(self):
        self.assertFalse(within_tol(5.11, 5.0, 0.1))

    def test_negative_delta_within(self):
        self.assertTrue(within_tol(4.95, 5.0, 0.1))

    def test_negative_delta_outside(self):
        self.assertFalse(within_tol(4.89, 5.0, 0.1))

    def test_zero_tolerance_exact(self):
        self.assertTrue(within_tol(3.14, 3.14, 0.0))

    def test_zero_tolerance_mismatch(self):
        self.assertFalse(within_tol(3.14001, 3.14, 0.0))

    def test_large_tolerance_always_passes(self):
        self.assertTrue(within_tol(99999.0, 0.0, 200000.0))

    def test_int_values_work(self):
        self.assertTrue(within_tol(10, 9, 2))
        self.assertFalse(within_tol(12, 9, 2))


# ---------------------------------------------------------------------------
# LINE_RE regex
# ---------------------------------------------------------------------------

class TestLineRe(unittest.TestCase):
    """Tests for LINE_RE — parses SIM headline output lines."""

    VALID_LINE = (
        "[SIM_A] 2024-01-15 equity=$12345.67 pnl=-2.34% dd=5.67% trades=10 new, 150 total"
    )

    def test_matches_valid_line(self):
        self.assertIsNotNone(LINE_RE.search(self.VALID_LINE))

    def test_captures_sim_id(self):
        m = LINE_RE.search(self.VALID_LINE)
        self.assertEqual(m.group(1), "SIM_A")

    def test_captures_equity(self):
        m = LINE_RE.search(self.VALID_LINE)
        self.assertEqual(float(m.group(2)), 12345.67)

    def test_captures_pnl(self):
        m = LINE_RE.search(self.VALID_LINE)
        self.assertEqual(float(m.group(3)), -2.34)

    def test_captures_dd(self):
        m = LINE_RE.search(self.VALID_LINE)
        self.assertEqual(float(m.group(4)), 5.67)

    def test_captures_trades_new(self):
        m = LINE_RE.search(self.VALID_LINE)
        self.assertEqual(int(m.group(5)), 10)

    def test_captures_trades_total(self):
        m = LINE_RE.search(self.VALID_LINE)
        self.assertEqual(int(m.group(6)), 150)

    def test_sim_b_matches(self):
        line = "[SIM_B] equity=$9999.00 pnl=1.23% dd=0.50% trades=5 new, 50 total"
        m = LINE_RE.search(line)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "SIM_B")

    def test_zero_pnl_matches(self):
        line = "[SIM_A] equity=$1000.00 pnl=0% dd=0% trades=0 new, 0 total"
        self.assertIsNotNone(LINE_RE.search(line))

    def test_garbage_line_no_match(self):
        self.assertIsNone(LINE_RE.search("random text without sim data"))


if __name__ == "__main__":
    unittest.main()
