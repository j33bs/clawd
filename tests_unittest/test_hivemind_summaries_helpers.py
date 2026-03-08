"""Tests for workspace/hivemind/hivemind/intelligence/summaries.py pure helpers.

Covers (no HiveMindStore, no file writes):
- _parse_period
- _iso
- _summarize_group
"""
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"

# Stub HiveMindStore before import.
_hm_pkg = sys.modules.get("hivemind") or types.ModuleType("hivemind")
_hm_pkg.__path__ = [str(HIVEMIND_ROOT / "hivemind")]
_store_mod = types.ModuleType("hivemind.store")
_store_mod.HiveMindStore = type("HiveMindStore", (), {})
sys.modules.setdefault("hivemind", _hm_pkg)
sys.modules.setdefault("hivemind.store", _store_mod)

if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence import summaries as sm  # noqa: E402

_UTC = timezone.utc


# ---------------------------------------------------------------------------
# _parse_period
# ---------------------------------------------------------------------------

class TestParsePeriod(unittest.TestCase):
    """Tests for _parse_period() — string like '7d' or '24h' → timedelta."""

    def test_days_suffix(self):
        result = sm._parse_period("7d")
        self.assertEqual(result, timedelta(days=7))

    def test_hours_suffix(self):
        result = sm._parse_period("24h")
        self.assertEqual(result, timedelta(hours=24))

    def test_short_days(self):
        result = sm._parse_period("1d")
        self.assertEqual(result, timedelta(days=1))

    def test_unknown_suffix_defaults_to_7_days(self):
        result = sm._parse_period("")
        self.assertEqual(result, timedelta(days=7))

    def test_no_suffix_defaults_to_7_days(self):
        result = sm._parse_period("5")
        self.assertEqual(result, timedelta(days=7))

    def test_returns_timedelta(self):
        self.assertIsInstance(sm._parse_period("3d"), timedelta)


# ---------------------------------------------------------------------------
# _iso
# ---------------------------------------------------------------------------

class TestIso(unittest.TestCase):
    """Tests for _iso() — ISO string → UTC-aware datetime."""

    def test_z_suffix_parsed(self):
        result = sm._iso("2026-01-15T12:00:00Z")
        self.assertEqual(result.hour, 12)

    def test_naive_becomes_utc(self):
        result = sm._iso("2026-01-15T12:00:00")
        self.assertEqual(result.tzinfo, _UTC)

    def test_returns_datetime(self):
        self.assertIsInstance(sm._iso("2026-01-15T12:00:00"), datetime)

    def test_year_month_day(self):
        result = sm._iso("2026-03-08T10:30:00")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)


# ---------------------------------------------------------------------------
# _summarize_group
# ---------------------------------------------------------------------------

class TestSummarizeGroup(unittest.TestCase):
    """Tests for _summarize_group() — list of rows → list of '- first_line' strings."""

    def test_empty_rows_returns_empty(self):
        result = sm._summarize_group([])
        self.assertEqual(result, [])

    def test_returns_list(self):
        result = sm._summarize_group([{"content": "hello world"}])
        self.assertIsInstance(result, list)

    def test_each_line_starts_with_dash(self):
        rows = [{"content": "line one"}, {"content": "line two"}]
        for line in sm._summarize_group(rows):
            self.assertTrue(line.startswith("- "))

    def test_long_content_truncated_at_140(self):
        rows = [{"content": "x" * 200}]
        result = sm._summarize_group(rows)
        self.assertEqual(len(result), 1)
        self.assertLessEqual(len(result[0]), 145)  # "- " + 137 + "..."

    def test_multiline_takes_first_line(self):
        rows = [{"content": "first line\nsecond line\nthird line"}]
        result = sm._summarize_group(rows)
        self.assertIn("first line", result[0])
        self.assertNotIn("second line", result[0])

    def test_at_most_10_rows_processed(self):
        rows = [{"content": f"item {i}"} for i in range(20)]
        result = sm._summarize_group(rows)
        self.assertLessEqual(len(result), 10)


if __name__ == "__main__":
    unittest.main()
