"""Tests for contract_calibrate pure / file-I/O utility functions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import contract_calibrate as cc


class TestPercentile(unittest.TestCase):
    """Unit tests for percentile() — pure boundary logic."""

    def test_empty_list_returns_zero(self):
        self.assertEqual(cc.percentile([], 0.5), 0.0)

    def test_single_element_always_returns_that_element(self):
        self.assertEqual(cc.percentile([42.0], 0.0), 42.0)
        self.assertEqual(cc.percentile([42.0], 0.5), 42.0)
        self.assertEqual(cc.percentile([42.0], 1.0), 42.0)

    def test_p0_returns_minimum(self):
        self.assertEqual(cc.percentile([3.0, 1.0, 2.0], 0.0), 1.0)

    def test_p1_returns_maximum(self):
        self.assertEqual(cc.percentile([3.0, 1.0, 2.0], 1.0), 3.0)

    def test_p50_returns_median(self):
        # [1, 2, 3, 4, 5] → median is index 2 → 3
        self.assertEqual(cc.percentile([1.0, 3.0, 5.0, 2.0, 4.0], 0.5), 3.0)

    def test_sorted_order_independent(self):
        self.assertEqual(
            cc.percentile([5.0, 3.0, 1.0, 4.0, 2.0], 0.25),
            cc.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.25),
        )

    def test_two_elements_p0_is_min(self):
        self.assertEqual(cc.percentile([10.0, 20.0], 0.0), 10.0)

    def test_two_elements_p1_is_max(self):
        self.assertEqual(cc.percentile([10.0, 20.0], 1.0), 20.0)


class TestModeFlips(unittest.TestCase):
    """Unit tests for mode_flips() — pure transition detection."""

    def test_empty_samples_returns_empty(self):
        self.assertEqual(cc.mode_flips([]), [])

    def test_single_sample_returns_empty(self):
        samples = [{"mode": "idle", "ts": "t0", "phase": "a"}]
        self.assertEqual(cc.mode_flips(samples), [])

    def test_no_flip_when_mode_constant(self):
        samples = [
            {"mode": "active", "ts": "t0", "phase": "a"},
            {"mode": "active", "ts": "t1", "phase": "a"},
            {"mode": "active", "ts": "t2", "phase": "a"},
        ]
        self.assertEqual(cc.mode_flips(samples), [])

    def test_one_flip_detected(self):
        samples = [
            {"mode": "active", "ts": "t0", "phase": "a"},
            {"mode": "idle", "ts": "t1", "phase": "b"},
        ]
        flips = cc.mode_flips(samples)
        self.assertEqual(len(flips), 1)
        self.assertEqual(flips[0]["from"], "active")
        self.assertEqual(flips[0]["to"], "idle")

    def test_multiple_flips_detected(self):
        samples = [
            {"mode": "idle", "ts": "t0", "phase": "a"},
            {"mode": "active", "ts": "t1", "phase": "a"},
            {"mode": "idle", "ts": "t2", "phase": "b"},
        ]
        flips = cc.mode_flips(samples)
        self.assertEqual(len(flips), 2)

    def test_flip_contains_ts_and_phase(self):
        samples = [
            {"mode": "a", "ts": "2026-01-01T00:00:00Z", "phase": "baseline"},
            {"mode": "b", "ts": "2026-01-01T00:01:00Z", "phase": "active"},
        ]
        flip = cc.mode_flips(samples)[0]
        self.assertIn("ts", flip)
        self.assertIn("phase", flip)
        self.assertEqual(flip["ts"], "2026-01-01T00:01:00Z")

    def test_none_mode_as_first_element_not_counted(self):
        """Known limitation: None mode is the internal sentinel; a first-element
        mode of None is indistinguishable from 'no previous', so a transition
        from None→something is not recorded as a flip."""
        samples = [
            {"mode": None, "ts": "t0", "phase": "a"},
            {"mode": "active", "ts": "t1", "phase": "a"},
        ]
        flips = cc.mode_flips(samples)
        # Implementation uses prev=None as sentinel → can't detect None→X flip
        self.assertEqual(len(flips), 0)


class TestReadWriteJson(unittest.TestCase):
    """Tests for read_json() and write_json() helpers."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_read_json_returns_default_when_missing(self):
        path = self._tmp / "nonexistent.json"
        result = cc.read_json(path, {"fallback": True})
        self.assertEqual(result, {"fallback": True})

    def test_read_json_returns_default_on_invalid_json(self):
        path = self._tmp / "bad.json"
        path.write_text("not json!", encoding="utf-8")
        result = cc.read_json(path, [])
        self.assertEqual(result, [])

    def test_write_then_read_round_trip(self):
        path = self._tmp / "data.json"
        payload = {"key": "value", "num": 42}
        cc.write_json(path, payload)
        result = cc.read_json(path, {})
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["num"], 42)

    def test_write_json_creates_parent_dirs(self):
        path = self._tmp / "deep" / "nested" / "data.json"
        self.assertFalse(path.parent.exists())
        cc.write_json(path, {"x": 1})
        self.assertTrue(path.exists())

    def test_write_json_file_has_trailing_newline(self):
        path = self._tmp / "out.json"
        cc.write_json(path, {"a": 1})
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))


class TestLoadSignalCount(unittest.TestCase):
    """Tests for load_signal_count()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_returns_zero_when_file_missing(self):
        path = self._tmp / "missing.jsonl"
        self.assertEqual(cc.load_signal_count(path), 0)

    def test_returns_line_count(self):
        path = self._tmp / "signals.jsonl"
        path.write_text('{"a":1}\n{"b":2}\n{"c":3}\n', encoding="utf-8")
        self.assertEqual(cc.load_signal_count(path), 3)

    def test_empty_file_returns_zero(self):
        path = self._tmp / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        self.assertEqual(cc.load_signal_count(path), 0)


class TestAppendSignal(unittest.TestCase):
    """Tests for append_signal()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_creates_parent_dirs(self):
        path = self._tmp / "signals" / "activity.jsonl"
        self.assertFalse(path.parent.exists())
        cc.append_signal(path, count=1, source="test")
        self.assertTrue(path.parent.exists())

    def test_appends_n_lines(self):
        path = self._tmp / "act.jsonl"
        cc.append_signal(path, count=3, source="test")
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 3)

    def test_each_line_is_valid_json(self):
        path = self._tmp / "act.jsonl"
        cc.append_signal(path, count=2, source="cal_active")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parsed = json.loads(line)
                self.assertIn("kind", parsed)
                self.assertEqual(parsed["kind"], "service_request")

    def test_count_zero_writes_nothing(self):
        path = self._tmp / "act.jsonl"
        cc.append_signal(path, count=0, source="test")
        if path.exists():
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "")

    def test_negative_count_writes_nothing(self):
        path = self._tmp / "act.jsonl"
        cc.append_signal(path, count=-5, source="test")
        if path.exists():
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "")

    def test_source_included_in_meta(self):
        path = self._tmp / "act.jsonl"
        cc.append_signal(path, count=1, source="calibration_active")
        line = path.read_text(encoding="utf-8").strip()
        parsed = json.loads(line)
        self.assertEqual(parsed["meta"]["source"], "calibration_active")


class TestUtcStamp(unittest.TestCase):
    """Tests for utc_stamp()."""

    def test_ends_with_z(self):
        ts = cc.utc_stamp()
        self.assertTrue(ts.endswith("Z"), f"Expected Z suffix, got: {ts}")

    def test_is_iso_format(self):
        import datetime as dt
        ts = cc.utc_stamp()
        # Should parse as ISO datetime
        parsed = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        self.assertIsNotNone(parsed)

    def test_microseconds_stripped(self):
        ts = cc.utc_stamp()
        # No decimal point in seconds (microseconds=0 in utc_now)
        self.assertNotIn(".", ts)


if __name__ == "__main__":
    unittest.main()
