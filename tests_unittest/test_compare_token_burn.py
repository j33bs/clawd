"""Tests for compare_token_burn — _to_int, _to_float, compare, evaluate_drift, render."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import compare_token_burn as ctb


class TestToInt(unittest.TestCase):
    """Tests for _to_int() — safe integer coercion."""

    def test_integer_string_parsed(self):
        self.assertEqual(ctb._to_int("42"), 42)

    def test_integer_value_returned(self):
        self.assertEqual(ctb._to_int(100), 100)

    def test_whitespace_stripped(self):
        self.assertEqual(ctb._to_int("  123  "), 123)

    def test_invalid_returns_default(self):
        self.assertEqual(ctb._to_int("abc"), 0)

    def test_none_returns_default(self):
        self.assertEqual(ctb._to_int(None), 0)

    def test_custom_default_returned_on_failure(self):
        self.assertEqual(ctb._to_int("bad", default=99), 99)

    def test_float_string_truncates(self):
        # int("3.5") raises → returns default 0
        self.assertEqual(ctb._to_int("3.5"), 0)

    def test_zero_string_returns_zero(self):
        self.assertEqual(ctb._to_int("0"), 0)

    def test_negative_string(self):
        self.assertEqual(ctb._to_int("-10"), -10)


class TestToFloat(unittest.TestCase):
    """Tests for _to_float() — safe float coercion."""

    def test_float_string_parsed(self):
        self.assertAlmostEqual(ctb._to_float("3.14"), 3.14)

    def test_integer_string_parsed(self):
        self.assertAlmostEqual(ctb._to_float("42"), 42.0)

    def test_invalid_returns_default(self):
        self.assertAlmostEqual(ctb._to_float("nope"), 0.0)

    def test_none_returns_default(self):
        self.assertAlmostEqual(ctb._to_float(None), 0.0)

    def test_custom_default_returned_on_failure(self):
        self.assertAlmostEqual(ctb._to_float("bad", default=1.5), 1.5)

    def test_whitespace_stripped(self):
        self.assertAlmostEqual(ctb._to_float("  2.5  "), 2.5)


class TestCompare(unittest.TestCase):
    """Tests for compare() — aggregate and per-model delta computation."""

    def _make_snapshot(self, total_calls=100, total_failures=5, total_tokens=10000,
                        failed_tokens=500, timeout_waste=200, failure_rate_pct=5.0):
        return {
            "aggregate": {
                "total_calls": total_calls,
                "total_failures": total_failures,
                "total_tokens": total_tokens,
                "failed_tokens": failed_tokens,
                "timeout_waste_tokens": timeout_waste,
                "failure_rate_pct": failure_rate_pct,
            },
            "per_model": {},
        }

    def test_zero_delta_when_identical(self):
        s = self._make_snapshot()
        delta, _ = ctb.compare(s, s)
        self.assertEqual(delta["calls"], 0)
        self.assertEqual(delta["failures"], 0)
        self.assertEqual(delta["tokens"], 0)
        self.assertAlmostEqual(delta["failure_rate_pp"], 0.0)

    def test_positive_delta_when_new_higher(self):
        old = self._make_snapshot(total_calls=100, total_tokens=10000)
        new = self._make_snapshot(total_calls=150, total_tokens=15000)
        delta, _ = ctb.compare(old, new)
        self.assertEqual(delta["calls"], 50)
        self.assertEqual(delta["tokens"], 5000)

    def test_negative_delta_when_new_lower(self):
        old = self._make_snapshot(total_failures=10)
        new = self._make_snapshot(total_failures=5)
        delta, _ = ctb.compare(old, new)
        self.assertEqual(delta["failures"], -5)

    def test_failure_rate_pp_computed(self):
        old = self._make_snapshot(failure_rate_pct=5.0)
        new = self._make_snapshot(failure_rate_pct=7.5)
        delta, _ = ctb.compare(old, new)
        self.assertAlmostEqual(delta["failure_rate_pp"], 2.5, places=3)

    def test_per_model_delta_new_model_only(self):
        old = {"aggregate": self._make_snapshot()["aggregate"], "per_model": {}}
        new = {
            "aggregate": self._make_snapshot()["aggregate"],
            "per_model": {
                ("openai", "gpt-4"): {"calls": 50, "success": 45, "failure": 5,
                                      "tokens": 5000, "failed_tokens": 200,
                                      "timeout_failures": 1, "timeout_waste": 100},
            },
        }
        delta, model_deltas = ctb.compare(old, new)
        self.assertEqual(len(model_deltas), 1)
        self.assertEqual(model_deltas[0]["provider"], "openai")
        self.assertEqual(model_deltas[0]["model"], "gpt-4")
        self.assertEqual(model_deltas[0]["delta_calls"], 50)

    def test_per_model_both_old_and_new(self):
        key = ("anthropic", "claude-3")
        row = {"calls": 100, "success": 90, "failure": 10, "tokens": 10000,
               "failed_tokens": 500, "timeout_failures": 2, "timeout_waste": 200}
        row_new = {"calls": 120, "success": 110, "failure": 10, "tokens": 12000,
                   "failed_tokens": 400, "timeout_failures": 1, "timeout_waste": 100}
        old = {"aggregate": self._make_snapshot()["aggregate"], "per_model": {key: row}}
        new = {"aggregate": self._make_snapshot()["aggregate"], "per_model": {key: row_new}}
        delta, model_deltas = ctb.compare(old, new)
        self.assertEqual(model_deltas[0]["delta_calls"], 20)
        self.assertEqual(model_deltas[0]["delta_tokens"], 2000)

    def test_model_deltas_sorted_by_waste(self):
        """Models sorted by |delta_failed_tokens| + |delta_timeout_waste| descending."""
        key1 = ("p1", "m1")
        key2 = ("p2", "m2")
        zero = {"calls": 0, "success": 0, "failure": 0, "tokens": 0,
                "failed_tokens": 0, "timeout_failures": 0, "timeout_waste": 0}
        high_waste = {"calls": 100, "success": 90, "failure": 10, "tokens": 10000,
                      "failed_tokens": 5000, "timeout_failures": 5, "timeout_waste": 3000}
        old = {"aggregate": self._make_snapshot()["aggregate"], "per_model": {key1: zero, key2: zero}}
        new = {"aggregate": self._make_snapshot()["aggregate"], "per_model": {key1: zero, key2: high_waste}}
        delta, model_deltas = ctb.compare(old, new)
        self.assertEqual(model_deltas[0]["provider"], "p2")  # p2 has higher waste


class TestEvaluateDrift(unittest.TestCase):
    """Tests for evaluate_drift() — violation detection."""

    def _base_delta(self):
        return {
            "calls": 10,
            "failures": 0,
            "tokens": 100,
            "failed_tokens": 0,
            "timeout_waste_tokens": 0,
            "failure_rate_pp": 0.0,
        }

    def test_no_violations_when_within_thresholds(self):
        delta = self._base_delta()
        violations = ctb.evaluate_drift(delta, [], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(violations, [])

    def test_failure_rate_pp_violation(self):
        delta = self._base_delta()
        delta["failure_rate_pp"] = 2.0  # > max 1.0
        violations = ctb.evaluate_drift(delta, [], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(len(violations), 1)
        self.assertIn("failure_rate_pp", violations[0])

    def test_timeout_waste_violation(self):
        delta = self._base_delta()
        delta["timeout_waste_tokens"] = 6000  # > max 5000
        violations = ctb.evaluate_drift(delta, [], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(len(violations), 1)
        self.assertIn("timeout_waste", violations[0])

    def test_failed_tokens_violation(self):
        delta = self._base_delta()
        delta["failed_tokens"] = 60000  # > max 50000
        violations = ctb.evaluate_drift(delta, [], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(len(violations), 1)
        self.assertIn("failed_tokens", violations[0])

    def test_model_failure_rate_violation(self):
        delta = self._base_delta()
        model_row = {
            "provider": "openai",
            "model": "gpt-4",
            "delta_calls": 50,
            "delta_tokens": 5000,
            "delta_failures": 10,
            "delta_failed_tokens": 100,
            "delta_timeout_waste": 50,
            "failure_rate_pp": 8.0,  # > max 5.0
            "new_calls": 50,  # >= min_calls_for_model_rate 20
        }
        violations = ctb.evaluate_drift(delta, [model_row], ctb.DEFAULT_THRESHOLDS)
        self.assertTrue(any("failure_rate_pp" in v for v in violations))

    def test_model_skipped_when_too_few_calls(self):
        delta = self._base_delta()
        model_row = {
            "provider": "openai", "model": "gpt-4",
            "delta_calls": 5, "delta_tokens": 100, "delta_failures": 5,
            "delta_failed_tokens": 50, "delta_timeout_waste": 10,
            "failure_rate_pp": 99.0,  # very high, but new_calls < min
            "new_calls": 10,  # < min_calls_for_model_rate 20
        }
        violations = ctb.evaluate_drift(delta, [model_row], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(violations, [])

    def test_negative_failure_rate_pp_triggers_violation(self):
        """Absolute value check: -2.0 pp also exceeds 1.0 threshold."""
        delta = self._base_delta()
        delta["failure_rate_pp"] = -2.0
        violations = ctb.evaluate_drift(delta, [], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(len(violations), 1)

    def test_multiple_violations_all_reported(self):
        delta = self._base_delta()
        delta["failure_rate_pp"] = 2.0
        delta["timeout_waste_tokens"] = 6000
        delta["failed_tokens"] = 60000
        violations = ctb.evaluate_drift(delta, [], ctb.DEFAULT_THRESHOLDS)
        self.assertEqual(len(violations), 3)


class TestRender(unittest.TestCase):
    """Tests for render() — markdown output structure."""

    def _base_delta(self):
        return {
            "calls": 10, "failures": 0, "tokens": 1000,
            "failed_tokens": 0, "timeout_waste_tokens": 0, "failure_rate_pp": 0.0,
        }

    def test_pass_when_no_violations(self):
        report = ctb.render("old.md", "new.md", self._base_delta(), [], ctb.DEFAULT_THRESHOLDS, [])
        self.assertIn("PASS", report)
        self.assertNotIn("FAIL", report)

    def test_fail_when_violations(self):
        report = ctb.render("old.md", "new.md", self._base_delta(), [], ctb.DEFAULT_THRESHOLDS,
                            ["some_violation"])
        self.assertIn("FAIL", report)

    def test_report_has_header(self):
        report = ctb.render("old.md", "new.md", self._base_delta(), [], ctb.DEFAULT_THRESHOLDS, [])
        self.assertIn("Token Burn Drift Report", report)

    def test_report_includes_baseline_and_current(self):
        report = ctb.render("baseline.md", "current.md", self._base_delta(), [], ctb.DEFAULT_THRESHOLDS, [])
        self.assertIn("baseline.md", report)
        self.assertIn("current.md", report)

    def test_ends_with_newline(self):
        report = ctb.render("a", "b", self._base_delta(), [], ctb.DEFAULT_THRESHOLDS, [])
        self.assertTrue(report.endswith("\n"))

    def test_violations_listed_in_report(self):
        violations = ["timeout_waste_tokens delta 6000 exceeds 5000"]
        report = ctb.render("a", "b", self._base_delta(), [], ctb.DEFAULT_THRESHOLDS, violations)
        self.assertIn("timeout_waste_tokens delta 6000 exceeds 5000", report)


if __name__ == "__main__":
    unittest.main()
