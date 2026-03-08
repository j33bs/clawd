"""Tests for workspace/tacti/temporal_watchdog.py pure helper functions.

Covers (no file I/O beyond tempfile):
- _to_dt
- beacon_path
- detect_temporal_drift
"""
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Build minimal tacti package stubs before importing the module.
def _build_tacti_stubs():
    tacti_pkg = types.ModuleType("tacti")
    tacti_pkg.__path__ = [str(REPO_ROOT / "workspace" / "tacti")]

    config_mod = types.ModuleType("tacti.config")
    config_mod.get_int = lambda key, default, clamp=None: default
    config_mod.is_enabled = lambda key: False

    events_mod = types.ModuleType("tacti.events")
    events_mod.emit = lambda *a, **kw: None

    sys.modules.setdefault("tacti", tacti_pkg)
    sys.modules.setdefault("tacti.config", config_mod)
    sys.modules.setdefault("tacti.events", events_mod)

_build_tacti_stubs()

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti import temporal_watchdog as tw  # noqa: E402

_UTC = timezone.utc
_NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# _to_dt
# ---------------------------------------------------------------------------

class TestToDt(unittest.TestCase):
    """Tests for _to_dt() — ISO string → UTC-aware datetime or None."""

    def test_z_suffix_parsed(self):
        result = tw._to_dt("2026-01-15T12:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.hour, 12)

    def test_naive_gets_utc(self):
        result = tw._to_dt("2026-01-15T12:00:00")
        self.assertEqual(result.tzinfo, _UTC)

    def test_invalid_returns_none(self):
        result = tw._to_dt("not-a-date")
        self.assertIsNone(result)

    def test_empty_returns_none(self):
        result = tw._to_dt("")
        self.assertIsNone(result)

    def test_returns_datetime(self):
        result = tw._to_dt("2026-01-15T12:00:00Z")
        self.assertIsInstance(result, datetime)

    def test_offset_preserved(self):
        result = tw._to_dt("2026-01-15T14:00:00+02:00")
        self.assertIsNotNone(result)
        # tzinfo is preserved (not normalized to UTC); datetime is tz-aware
        self.assertIsNotNone(result.tzinfo)


# ---------------------------------------------------------------------------
# beacon_path
# ---------------------------------------------------------------------------

class TestBeaconPath(unittest.TestCase):
    """Tests for beacon_path() — returns path under workspace/state/temporal."""

    def test_returns_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = tw.beacon_path(Path(td))
            self.assertIsInstance(result, Path)

    def test_path_ends_with_beacon_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = tw.beacon_path(Path(td))
            self.assertEqual(result.name, "beacon.json")

    def test_path_under_workspace_state(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = tw.beacon_path(Path(td))
            self.assertIn("temporal", str(result))


# ---------------------------------------------------------------------------
# detect_temporal_drift
# ---------------------------------------------------------------------------

class TestDetectTemporalDrift(unittest.TestCase):
    """Tests for detect_temporal_drift() — finds drift anomalies in text."""

    def test_no_dates_no_findings(self):
        result = tw.detect_temporal_drift("nothing to see here", now=_NOW)
        self.assertEqual(result, [])

    def test_returns_list(self):
        result = tw.detect_temporal_drift("", now=_NOW)
        self.assertIsInstance(result, list)

    def test_sequence_violation_detected(self):
        # Two timestamps in reverse order
        text = "2026-03-08T12:00:00Z then 2026-03-08T11:00:00Z"
        result = tw.detect_temporal_drift(text, now=_NOW)
        types_found = {r["type"] for r in result}
        self.assertIn("sequence_violation", types_found)

    def test_future_done_detected(self):
        # Event 3 hours in the future marked as done
        future_ts = "2026-03-08T15:00:00Z"
        text = f"this is done {future_ts}"
        result = tw.detect_temporal_drift(text, now=_NOW)
        types_found = {r["type"] for r in result}
        self.assertIn("future_event_marked_done", types_found)

    def test_stale_beacon_detected(self):
        # Beacon updated 4 hours ago (default stale limit = 20 min)
        old_time = (_NOW - timedelta(hours=4)).isoformat().replace("+00:00", "Z")
        beacon = {"updated_at": old_time}
        result = tw.detect_temporal_drift("", now=_NOW, beacon=beacon)
        types_found = {r["type"] for r in result}
        self.assertIn("stale_context_treated_fresh", types_found)

    def test_fresh_beacon_no_finding(self):
        # Beacon updated 1 minute ago
        fresh_time = (_NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        beacon = {"updated_at": fresh_time}
        result = tw.detect_temporal_drift("", now=_NOW, beacon=beacon)
        stale = [r for r in result if r["type"] == "stale_context_treated_fresh"]
        self.assertEqual(stale, [])

    def test_findings_have_type_and_score(self):
        text = "2026-03-08T12:00:00Z then 2026-03-08T11:00:00Z"
        result = tw.detect_temporal_drift(text, now=_NOW)
        for finding in result:
            self.assertIn("type", finding)
            self.assertIn("score", finding)


if __name__ == "__main__":
    unittest.main()
