"""Tests for report_token_burn — _safe_int, _parse_since, _event_timestamp,
aggregate, evaluate_thresholds."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import report_token_burn as rtb


class TestSafeInt(unittest.TestCase):
    """Tests for _safe_int() — integer coercion with default."""

    def test_integer_returned_as_is(self):
        self.assertEqual(rtb._safe_int(42), 42)

    def test_string_integer_parsed(self):
        self.assertEqual(rtb._safe_int("100"), 100)

    def test_invalid_returns_default(self):
        self.assertEqual(rtb._safe_int("abc"), 0)

    def test_none_returns_default(self):
        self.assertEqual(rtb._safe_int(None), 0)

    def test_custom_default(self):
        self.assertEqual(rtb._safe_int("bad", default=99), 99)

    def test_zero_parsed(self):
        self.assertEqual(rtb._safe_int("0"), 0)

    def test_negative_parsed(self):
        self.assertEqual(rtb._safe_int("-5"), -5)


class TestParseSince(unittest.TestCase):
    """Tests for _parse_since() — timestamp parsing to ms epoch."""

    def test_none_returns_none(self):
        self.assertIsNone(rtb._parse_since(None))

    def test_empty_returns_none(self):
        self.assertIsNone(rtb._parse_since(""))

    def test_whitespace_returns_none(self):
        self.assertIsNone(rtb._parse_since("   "))

    def test_large_int_string_ms_returned_as_is(self):
        # > 1e12 → treat as already ms
        result = rtb._parse_since("1709900000000")
        self.assertEqual(result, 1709900000000)

    def test_small_number_converted_to_ms(self):
        # seconds → ms; 1000000 < 1e12 → multiply by 1000
        result = rtb._parse_since("1000")
        self.assertEqual(result, 1_000_000)

    def test_iso_z_suffix_parsed(self):
        result = rtb._parse_since("2026-03-08T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_iso_without_tz_parsed(self):
        result = rtb._parse_since("2026-03-08T12:00:00")
        self.assertIsNotNone(result)

    def test_garbage_returns_none(self):
        self.assertIsNone(rtb._parse_since("not-a-date"))


class TestEventTimestamp(unittest.TestCase):
    """Tests for _event_timestamp() — flexible timestamp normalization."""

    def test_none_returns_none(self):
        self.assertIsNone(rtb._event_timestamp(None))

    def test_large_int_ms_returned_as_is(self):
        self.assertEqual(rtb._event_timestamp(1709900000000), 1709900000000)

    def test_small_float_seconds_to_ms(self):
        result = rtb._event_timestamp(1000.5)
        self.assertEqual(result, 1_000_500)

    def test_iso_string_parsed(self):
        result = rtb._event_timestamp("2026-03-08T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(rtb._event_timestamp("not-a-ts"))


class TestAggregate(unittest.TestCase):
    """Tests for aggregate() — summing per-agent rows into totals."""

    def _make_stats(self, rows):
        return {"rows": rows, "scanned_files": 1, "scanned_lines": 100}

    def _make_row(self, calls=10, successes=9, failures=1, tokens=1000,
                  failed_tokens=50, timeout_failures=0, timeout_waste_tokens=0,
                  missing_usage_records=0):
        return {
            "calls": calls, "successes": successes, "failures": failures,
            "tokens": tokens, "failed_tokens": failed_tokens,
            "timeout_failures": timeout_failures,
            "timeout_waste_tokens": timeout_waste_tokens,
            "missing_usage_records": missing_usage_records,
        }

    def test_empty_rows_returns_zeros(self):
        result = rtb.aggregate(self._make_stats({}))
        self.assertEqual(result["total_calls"], 0)
        self.assertEqual(result["total_failures"], 0)
        self.assertEqual(result["total_tokens"], 0)
        self.assertAlmostEqual(result["failure_rate_pct"], 0.0)

    def test_single_row_summed(self):
        rows = {("coder", "openai", "gpt-4"): self._make_row(calls=10, failures=2, tokens=5000)}
        result = rtb.aggregate(self._make_stats(rows))
        self.assertEqual(result["total_calls"], 10)
        self.assertEqual(result["total_failures"], 2)
        self.assertEqual(result["total_tokens"], 5000)

    def test_two_rows_summed(self):
        rows = {
            ("a", "p1", "m1"): self._make_row(calls=5, tokens=500),
            ("b", "p2", "m2"): self._make_row(calls=15, tokens=1500),
        }
        result = rtb.aggregate(self._make_stats(rows))
        self.assertEqual(result["total_calls"], 20)
        self.assertEqual(result["total_tokens"], 2000)

    def test_failure_rate_computed(self):
        rows = {("a", "p", "m"): self._make_row(calls=10, failures=1)}
        result = rtb.aggregate(self._make_stats(rows))
        self.assertAlmostEqual(result["failure_rate_pct"], 10.0, places=3)

    def test_zero_calls_failure_rate_zero(self):
        rows = {("a", "p", "m"): self._make_row(calls=0, failures=0)}
        result = rtb.aggregate(self._make_stats(rows))
        self.assertAlmostEqual(result["failure_rate_pct"], 0.0)

    def test_failed_tokens_summed(self):
        rows = {
            ("a", "p1", "m1"): self._make_row(failed_tokens=100),
            ("b", "p2", "m2"): self._make_row(failed_tokens=200),
        }
        result = rtb.aggregate(self._make_stats(rows))
        self.assertEqual(result["failed_tokens"], 300)

    def test_timeout_waste_summed(self):
        rows = {
            ("a", "p1", "m1"): self._make_row(timeout_waste_tokens=500),
            ("b", "p2", "m2"): self._make_row(timeout_waste_tokens=300),
        }
        result = rtb.aggregate(self._make_stats(rows))
        self.assertEqual(result["timeout_waste_tokens"], 800)

    def test_missing_usage_records_summed(self):
        rows = {
            ("a", "p", "m"): self._make_row(missing_usage_records=3),
        }
        result = rtb.aggregate(self._make_stats(rows))
        self.assertEqual(result["missing_usage_records"], 3)


class TestEvaluateThresholds(unittest.TestCase):
    """Tests for evaluate_thresholds() — threshold violation detection."""

    def _make_agg(self, failure_rate_pct=0.0, failed_tokens=0,
                  timeout_waste_tokens=0, missing_usage_records=0):
        return {
            "total_calls": 100,
            "total_successes": 100,
            "total_failures": 0,
            "total_tokens": 10000,
            "failed_tokens": failed_tokens,
            "timeout_failures": 0,
            "timeout_waste_tokens": timeout_waste_tokens,
            "missing_usage_records": missing_usage_records,
            "failure_rate_pct": failure_rate_pct,
        }

    def _make_router(self, escalations=0):
        return {"escalations_total": escalations, "events_file": "-"}

    def test_no_thresholds_returns_no_violations(self):
        result = rtb.evaluate_thresholds(self._make_agg(), self._make_router(), {})
        self.assertEqual(result, [])

    def test_none_thresholds_returns_no_violations(self):
        result = rtb.evaluate_thresholds(self._make_agg(), self._make_router(), None)
        self.assertEqual(result, [])

    def test_failure_rate_violation(self):
        agg = self._make_agg(failure_rate_pct=10.0)
        violations = rtb.evaluate_thresholds(agg, self._make_router(), {"max_failure_rate_pct": 5.0})
        self.assertEqual(len(violations), 1)
        self.assertIn("failure_rate_pct", violations[0])

    def test_failure_rate_within_threshold_no_violation(self):
        agg = self._make_agg(failure_rate_pct=4.0)
        violations = rtb.evaluate_thresholds(agg, self._make_router(), {"max_failure_rate_pct": 5.0})
        self.assertEqual(violations, [])

    def test_failed_tokens_violation(self):
        agg = self._make_agg(failed_tokens=10001)
        violations = rtb.evaluate_thresholds(agg, self._make_router(), {"max_failed_tokens": 10000})
        self.assertEqual(len(violations), 1)
        self.assertIn("failed_tokens", violations[0])

    def test_timeout_waste_violation(self):
        agg = self._make_agg(timeout_waste_tokens=5001)
        violations = rtb.evaluate_thresholds(agg, self._make_router(), {"max_timeout_waste_tokens": 5000})
        self.assertEqual(len(violations), 1)
        self.assertIn("timeout_waste_tokens", violations[0])

    def test_router_escalation_violation(self):
        agg = self._make_agg()
        router = self._make_router(escalations=10)
        violations = rtb.evaluate_thresholds(agg, router, {"max_router_escalations": 5})
        self.assertEqual(len(violations), 1)
        self.assertIn("router_escalations", violations[0])

    def test_missing_usage_records_violation(self):
        agg = self._make_agg(missing_usage_records=5)
        violations = rtb.evaluate_thresholds(agg, self._make_router(), {"max_missing_usage_records": 4})
        self.assertEqual(len(violations), 1)
        self.assertIn("missing_usage_records", violations[0])

    def test_multiple_violations_all_reported(self):
        agg = self._make_agg(failure_rate_pct=20.0, failed_tokens=99999)
        thresholds = {"max_failure_rate_pct": 5.0, "max_failed_tokens": 1000}
        violations = rtb.evaluate_thresholds(agg, self._make_router(), thresholds)
        self.assertEqual(len(violations), 2)

    def test_exact_threshold_not_violated(self):
        agg = self._make_agg(failed_tokens=10000)
        violations = rtb.evaluate_thresholds(agg, self._make_router(), {"max_failed_tokens": 10000})
        self.assertEqual(violations, [])  # > not >= → exact is OK


if __name__ == "__main__":
    unittest.main()
