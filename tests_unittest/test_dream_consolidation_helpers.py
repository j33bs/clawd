"""Tests for pure helpers in workspace/scripts/dream_consolidation.py.

Covers:
- _parse_ts(ts_str) — ISO-8601 timestamp → aware datetime or None
"""
import importlib.util as _ilu
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "dream_consolidation.py"

_spec = _ilu.spec_from_file_location("dream_consolidation_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["dream_consolidation_real"] = _mod
_spec.loader.exec_module(_mod)

_parse_ts = _mod._parse_ts


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------


class TestParseTs(unittest.TestCase):
    """Tests for _parse_ts() — ISO-8601 parser returning aware datetime."""

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_ts(""))

    def test_none_returns_none(self):
        self.assertIsNone(_parse_ts(None))

    def test_z_suffix_parsed(self):
        result = _parse_ts("2026-01-15T12:00:00Z")
        self.assertIsNotNone(result)

    def test_plus_offset_parsed(self):
        result = _parse_ts("2026-01-15T12:00:00+00:00")
        self.assertIsNotNone(result)

    def test_returns_datetime_instance(self):
        result = _parse_ts("2026-03-01T09:00:00Z")
        self.assertIsInstance(result, datetime)

    def test_returns_aware_datetime(self):
        result = _parse_ts("2026-03-01T09:00:00Z")
        self.assertIsNotNone(result.tzinfo)

    def test_z_and_offset_produce_same_moment(self):
        a = _parse_ts("2026-01-01T00:00:00Z")
        b = _parse_ts("2026-01-01T00:00:00+00:00")
        self.assertEqual(a, b)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_parse_ts("not-a-date"))

    def test_partial_date_returns_none(self):
        self.assertIsNone(_parse_ts("2026-13-45"))

    def test_correct_year_parsed(self):
        result = _parse_ts("2026-03-09T08:30:00Z")
        self.assertEqual(result.year, 2026)

    def test_correct_month_parsed(self):
        result = _parse_ts("2026-03-09T08:30:00Z")
        self.assertEqual(result.month, 3)

    def test_correct_day_parsed(self):
        result = _parse_ts("2026-03-09T08:30:00Z")
        self.assertEqual(result.day, 9)


if __name__ == "__main__":
    unittest.main()
