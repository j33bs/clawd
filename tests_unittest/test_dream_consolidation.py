"""Tests for dream_consolidation._parse_ts() and analyze_day() time-window filter."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import dream_consolidation as dc


def _utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestParsTs(unittest.TestCase):
    def test_z_suffix(self):
        ts = dc._parse_ts("2026-03-07T14:00:00Z")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.tzinfo, timezone.utc)

    def test_offset_suffix(self):
        ts = dc._parse_ts("2026-03-07T14:00:00+00:00")
        self.assertIsNotNone(ts)

    def test_empty_string_returns_none(self):
        self.assertIsNone(dc._parse_ts(""))

    def test_malformed_returns_none(self):
        self.assertIsNone(dc._parse_ts("not-a-date"))
        self.assertIsNone(dc._parse_ts("2026/03/07"))

    def test_none_input_returns_none(self):
        self.assertIsNone(dc._parse_ts(None))


class TestAnalyzeDayWindowFilter(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_root = dc.REPO_ROOT
        self._tmp = Path(self._tmpdir.name)
        # Create the events directory
        events_dir = self._tmp / "workspace" / "state" / "tacti_cr"
        events_dir.mkdir(parents=True)
        self._events_file = events_dir / "events.jsonl"
        dc.REPO_ROOT = self._tmp

    def tearDown(self):
        dc.REPO_ROOT = self._orig_root
        self._tmpdir.cleanup()

    def _write_events(self, timestamps: list[datetime]) -> None:
        with self._events_file.open("w") as f:
            for ts in timestamps:
                e = {"ts": _utc(ts), "type": "test.event"}
                f.write(json.dumps(e) + "\n")

    def test_no_events_file_returns_error(self):
        result = dc.analyze_day()
        self.assertIn("error", result)

    def test_all_events_within_window(self):
        now = datetime.now(timezone.utc)
        recent = [now - timedelta(hours=1), now - timedelta(hours=2)]
        self._write_events(recent)
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 2)
        self.assertEqual(result["skipped_stale"], 0)

    def test_stale_events_excluded(self):
        now = datetime.now(timezone.utc)
        stale = [now - timedelta(hours=25), now - timedelta(hours=48)]
        self._write_events(stale)
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 0)
        self.assertEqual(result["skipped_stale"], 2)

    def test_mixed_events_filtered_correctly(self):
        now = datetime.now(timezone.utc)
        recent = [now - timedelta(hours=1), now - timedelta(hours=3)]
        stale = [now - timedelta(hours=25), now - timedelta(hours=30)]
        self._write_events(recent + stale)
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 2)
        self.assertEqual(result["skipped_stale"], 2)

    def test_malformed_json_lines_skipped(self):
        with self._events_file.open("w") as f:
            f.write("not valid json\n")
            f.write("{\"ts\": \"bad-date\", \"type\": \"x\"}\n")
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 0)

    def test_result_contains_required_keys(self):
        now = datetime.now(timezone.utc)
        self._write_events([now - timedelta(minutes=30)])
        result = dc.analyze_day(window_hours=24)
        for key in ("total_events", "event_types", "successes", "failures",
                    "window_hours", "cutoff_utc", "skipped_stale"):
            self.assertIn(key, result)

    def test_window_hours_respected(self):
        now = datetime.now(timezone.utc)
        # Use events well within/outside boundaries to avoid timing edge cases
        # (avoid exactly N hours ago, which races with cutoff precision)
        times = [
            now - timedelta(hours=1),    # clearly within 6h
            now - timedelta(hours=4),    # clearly within 6h
            now - timedelta(hours=7),    # clearly outside 6h, within 48h
            now - timedelta(hours=25),   # clearly outside 24h, within 48h
        ]
        self._write_events(times)
        # 6h window: events at 1h and 4h included; 7h and 25h excluded
        result_6h = dc.analyze_day(window_hours=6)
        self.assertEqual(result_6h["total_events"], 2)
        self.assertEqual(result_6h["skipped_stale"], 2)
        # 48h window: all 4 included
        result_48h = dc.analyze_day(window_hours=48)
        self.assertEqual(result_48h["total_events"], 4)

    def test_success_failure_counting(self):
        now = datetime.now(timezone.utc)
        with self._events_file.open("w") as f:
            f.write(json.dumps({"ts": _utc(now - timedelta(hours=1)), "type": "step.success"}) + "\n")
            f.write(json.dumps({"ts": _utc(now - timedelta(hours=2)), "type": "step.failure"}) + "\n")
            f.write(json.dumps({"ts": _utc(now - timedelta(hours=3)), "type": "step.success"}) + "\n")
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 3)
        self.assertGreater(result["successes"], 0)
        self.assertGreater(result["failures"], 0)

    def test_tacti_cr_immune_events_counted_correctly(self):
        """tacti_cr.semantic_immune.accepted → successes; .quarantined → failures."""
        now = datetime.now(timezone.utc)
        with self._events_file.open("w") as f:
            for _ in range(3):
                f.write(json.dumps({
                    "ts": _utc(now - timedelta(hours=1)),
                    "type": "tacti_cr.semantic_immune.accepted",
                }) + "\n")
            for _ in range(2):
                f.write(json.dumps({
                    "ts": _utc(now - timedelta(hours=2)),
                    "type": "tacti_cr.semantic_immune.quarantined",
                }) + "\n")
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 5)
        self.assertEqual(result["successes"], 3)
        self.assertEqual(result["failures"], 2)

    def test_patterns_string_is_not_placeholder(self):
        """patterns field should be a real summary, not the literal 'Analyze for patterns'."""
        now = datetime.now(timezone.utc)
        with self._events_file.open("w") as f:
            f.write(json.dumps({"ts": _utc(now - timedelta(hours=1)), "type": "tacti_cr.prefetch.hit_rate"}) + "\n")
            f.write(json.dumps({"ts": _utc(now - timedelta(hours=2)), "type": "tacti_cr.semantic_immune.accepted"}) + "\n")
        result = dc.analyze_day(window_hours=24)
        self.assertNotEqual(result["patterns"], "Analyze for patterns")
        self.assertIn("top_events", result["patterns"])

    def test_empty_window_patterns_is_meaningful(self):
        """With no events in window, patterns should say 'no events in window'."""
        now = datetime.now(timezone.utc)
        # Write only stale events
        with self._events_file.open("w") as f:
            f.write(json.dumps({"ts": _utc(now - timedelta(hours=48)), "type": "old.event"}) + "\n")
        result = dc.analyze_day(window_hours=24)
        self.assertEqual(result["total_events"], 0)
        self.assertEqual(result["patterns"], "no events in window")

    def test_immune_acceptance_rate_in_patterns(self):
        """When both accepted + quarantined events present, patterns includes N/M immune_accepted."""
        now = datetime.now(timezone.utc)
        with self._events_file.open("w") as f:
            for _ in range(4):
                f.write(json.dumps({"ts": _utc(now - timedelta(hours=1)),
                                    "type": "tacti_cr.semantic_immune.accepted"}) + "\n")
            for _ in range(1):
                f.write(json.dumps({"ts": _utc(now - timedelta(hours=1)),
                                    "type": "tacti_cr.semantic_immune.quarantined"}) + "\n")
        result = dc.analyze_day(window_hours=24)
        self.assertIn("immune_accepted", result["patterns"])
        # 4 accepted, 1 quarantined → "4/5 immune_accepted"
        self.assertIn("4/5", result["patterns"])


if __name__ == "__main__":
    unittest.main()
