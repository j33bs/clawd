"""Tests for hivemind.stigmergy — _to_dt, _utc, StigmergyMap._effective,
StigmergyMap.deposit_mark, StigmergyMap.query_marks, StigmergyMap.suggest_avoid_topics."""
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.stigmergy import StigmergyMap, _to_dt, _utc


class TestToDt(unittest.TestCase):
    """Tests for _to_dt() — flexible datetime parsing."""

    def test_datetime_with_tz_returned_as_is(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = _to_dt(now)
        self.assertEqual(result, now)

    def test_naive_datetime_gets_utc(self):
        naive = datetime(2026, 3, 8, 12, 0, 0)
        result = _to_dt(naive)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_iso_z_string_parsed(self):
        result = _to_dt("2026-03-08T12:00:00Z")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 8)

    def test_iso_offset_string_parsed(self):
        result = _to_dt("2026-03-08T12:00:00+00:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.hour, 12)

    def test_invalid_string_returns_now(self):
        before = datetime.now(timezone.utc)
        result = _to_dt("invalid date string")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_none_returns_now(self):
        before = datetime.now(timezone.utc)
        result = _to_dt(None)
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_result_always_tz_aware(self):
        result = _to_dt("2026-01-01T00:00:00Z")
        self.assertIsNotNone(result.tzinfo)


class TestUtc(unittest.TestCase):
    """Tests for _utc() — ISO timestamp with Z suffix."""

    def test_returns_string(self):
        self.assertIsInstance(_utc(), str)

    def test_ends_with_z(self):
        result = _utc()
        self.assertTrue(result.endswith("Z"), f"Expected Z suffix: {result!r}")

    def test_with_explicit_datetime(self):
        dt = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = _utc(now=dt)
        self.assertIn("2026-03-08", result)
        self.assertIn("12:00:00", result)

    def test_no_plus_00_00_in_output(self):
        result = _utc()
        self.assertNotIn("+00:00", result)


class TestStigmergyMapEffective(unittest.TestCase):
    """Tests for StigmergyMap._effective() — decay computation."""

    def test_zero_age_returns_intensity(self):
        mark = {"timestamp": "2026-03-08T12:00:00Z", "intensity": 1.0, "decay_rate": 0.1}
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = StigmergyMap._effective(mark, now)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_decay_over_time(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        mark_ts = now - timedelta(hours=10)
        mark = {
            "timestamp": mark_ts.isoformat().replace("+00:00", "Z"),
            "intensity": 1.0,
            "decay_rate": 0.1,
        }
        result = StigmergyMap._effective(mark, now)
        expected = math.exp(-0.1 * 10)
        self.assertAlmostEqual(result, expected, places=5)

    def test_zero_intensity_returns_zero(self):
        mark = {"timestamp": "2026-03-08T12:00:00Z", "intensity": 0.0, "decay_rate": 0.1}
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(StigmergyMap._effective(mark, now), 0.0)

    def test_clamps_at_zero_not_negative(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        old = now - timedelta(hours=10000)
        mark = {
            "timestamp": old.isoformat().replace("+00:00", "Z"),
            "intensity": 1.0,
            "decay_rate": 100.0,  # extremely fast decay
        }
        result = StigmergyMap._effective(mark, now)
        self.assertGreaterEqual(result, 0.0)

    def test_default_decay_rate(self):
        # No decay_rate key → defaults to 0.1
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        mark = {"timestamp": "2026-03-08T12:00:00Z", "intensity": 1.0}
        result = StigmergyMap._effective(mark, now)
        self.assertAlmostEqual(result, 1.0, places=5)


class TestStigmergyMapDepositQuery(unittest.TestCase):
    """Tests for StigmergyMap.deposit_mark() and query_marks()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._map = StigmergyMap(path=self._tmp / "stigmergy.json")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_deposit_creates_file(self):
        self._map.deposit_mark("routing", 0.8, 0.1, "coder")
        self.assertTrue(self._map.path.exists())

    def test_deposit_returns_ok(self):
        result = self._map.deposit_mark("routing", 0.8, 0.1, "coder")
        self.assertTrue(result["ok"])

    def test_deposit_increments_count(self):
        self._map.deposit_mark("topic_a", 0.8, 0.1, "coder")
        result = self._map.deposit_mark("topic_b", 0.6, 0.1, "planner")
        self.assertEqual(result["count"], 2)

    def test_query_returns_list(self):
        self._map.deposit_mark("routing", 0.8, 0.1, "coder")
        result = self._map.query_marks()
        self.assertIsInstance(result, list)

    def test_query_empty_when_no_marks(self):
        result = self._map.query_marks()
        self.assertEqual(result, [])

    def test_query_includes_effective_intensity(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("topic", 1.0, 0.1, "coder", now=now)
        result = self._map.query_marks(now=now)
        self.assertIn("effective_intensity", result[0])

    def test_query_sorted_by_effective_intensity_descending(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("low", 0.2, 0.1, "coder", now=now)
        self._map.deposit_mark("high", 0.9, 0.1, "coder", now=now)
        result = self._map.query_marks(now=now)
        self.assertEqual(result[0]["topic"], "high")

    def test_query_top_n_limits_results(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(10):
            self._map.deposit_mark(f"topic_{i}", 0.5, 0.1, "coder", now=now)
        result = self._map.query_marks(now=now, top_n=3)
        self.assertLessEqual(len(result), 3)

    def test_deposited_topic_in_query(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("consciousness", 0.7, 0.05, "planner", now=now)
        result = self._map.query_marks(now=now)
        topics = [m["topic"] for m in result]
        self.assertIn("consciousness", topics)

    def test_deposit_preserves_all_fields(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("routing", 0.8, 0.15, "coder", now=now)
        marks = json.loads(self._map.path.read_text())
        mark = marks[0]
        self.assertEqual(mark["topic"], "routing")
        self.assertAlmostEqual(mark["intensity"], 0.8)
        self.assertAlmostEqual(mark["decay_rate"], 0.15)
        self.assertEqual(mark["deposited_by"], "coder")


class TestStigmergyMapSuggestAvoid(unittest.TestCase):
    """Tests for StigmergyMap.suggest_avoid_topics() — high-intensity filter."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._map = StigmergyMap(path=self._tmp / "stigmergy.json")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_empty_map_returns_empty(self):
        result = self._map.suggest_avoid_topics()
        self.assertEqual(result, [])

    def test_high_intensity_topic_avoided(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("hot_topic", 1.0, 0.0001, "coder", now=now)
        result = self._map.suggest_avoid_topics(now=now, threshold=0.75)
        self.assertIn("hot_topic", result)

    def test_low_intensity_topic_not_avoided(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("cool_topic", 0.1, 0.0001, "coder", now=now)
        result = self._map.suggest_avoid_topics(now=now, threshold=0.75)
        self.assertNotIn("cool_topic", result)

    def test_threshold_filters_correctly(self):
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        self._map.deposit_mark("border_topic", 0.8, 0.0001, "coder", now=now)
        above = self._map.suggest_avoid_topics(now=now, threshold=0.75)
        below = self._map.suggest_avoid_topics(now=now, threshold=0.9)
        self.assertIn("border_topic", above)
        self.assertNotIn("border_topic", below)

    def test_returns_list_of_strings(self):
        result = self._map.suggest_avoid_topics()
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, str)


if __name__ == "__main__":
    unittest.main()
