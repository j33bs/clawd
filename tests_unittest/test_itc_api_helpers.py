"""Tests for workspace/itc/api.py pure helper functions.

Covers:
- _parse_iso
- _parse_lookback
- _artifact_root_from_policy
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.itc.api import (  # noqa: E402
    _artifact_root_from_policy,
    _parse_iso,
    _parse_lookback,
)


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------

class TestParseIso(unittest.TestCase):
    """Tests for _parse_iso() — ISO Z timestamp to UTC datetime."""

    def test_returns_datetime(self):
        self.assertIsInstance(_parse_iso("2026-01-15T12:00:00Z"), datetime)

    def test_is_utc_aware(self):
        dt = _parse_iso("2026-01-15T12:00:00Z")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_year_month_day(self):
        dt = _parse_iso("2026-03-08T00:00:00Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 3)
        self.assertEqual(dt.day, 8)

    def test_hour_minute_second(self):
        dt = _parse_iso("2026-01-15T14:30:45Z")
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.second, 45)

    def test_invalid_raises(self):
        with self.assertRaises(Exception):
            _parse_iso("not-a-date")


# ---------------------------------------------------------------------------
# _parse_lookback
# ---------------------------------------------------------------------------

class TestParseLookback(unittest.TestCase):
    """Tests for _parse_lookback() — '1h', '30m', '7d' → timedelta."""

    def test_minutes(self):
        self.assertEqual(_parse_lookback("30m"), timedelta(minutes=30))

    def test_hours(self):
        self.assertEqual(_parse_lookback("8h"), timedelta(hours=8))

    def test_days(self):
        self.assertEqual(_parse_lookback("7d"), timedelta(days=7))

    def test_returns_timedelta(self):
        self.assertIsInstance(_parse_lookback("1h"), timedelta)

    def test_single_minute(self):
        self.assertEqual(_parse_lookback("1m"), timedelta(minutes=1))

    def test_single_day(self):
        self.assertEqual(_parse_lookback("1d"), timedelta(days=1))

    def test_invalid_unit_raises(self):
        with self.assertRaises(Exception):
            _parse_lookback("5w")


# ---------------------------------------------------------------------------
# _artifact_root_from_policy
# ---------------------------------------------------------------------------

class TestArtifactRootFromPolicy(unittest.TestCase):
    """Tests for _artifact_root_from_policy() — path resolution from policy dict."""

    def test_none_policy_returns_default(self):
        result = _artifact_root_from_policy(None)
        self.assertIsInstance(result, Path)
        self.assertIn("artifacts", str(result))

    def test_empty_dict_returns_default(self):
        result = _artifact_root_from_policy({})
        self.assertIsInstance(result, Path)
        self.assertIn("artifacts", str(result))

    def test_custom_artifacts_root_used(self):
        result = _artifact_root_from_policy({"artifacts_root": "/tmp/custom_itc"})
        self.assertEqual(result, Path("/tmp/custom_itc"))

    def test_returns_path(self):
        self.assertIsInstance(_artifact_root_from_policy(None), Path)

    def test_policy_without_artifacts_key_returns_default(self):
        result = _artifact_root_from_policy({"run_id": "test_run"})
        self.assertIn("artifacts", str(result))


if __name__ == "__main__":
    unittest.main()
