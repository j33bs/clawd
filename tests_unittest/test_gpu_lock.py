"""Tests for gpu_lock — parse_z, is_expired, utc_stamp, save_lock/load_lock."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gpu_lock as gl


class TestParseZ(unittest.TestCase):
    """Tests for parse_z() — ISO-Z datetime string parsing."""

    def test_z_suffix_parsed(self):
        result = gl.parse_z("2026-03-08T12:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 8)

    def test_result_is_utc_aware(self):
        result = gl.parse_z("2026-03-08T00:00:00Z")
        self.assertEqual(result.tzinfo, dt.timezone.utc)

    def test_offset_format_parsed(self):
        result = gl.parse_z("2026-03-08T12:00:00+00:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.hour, 12)

    def test_empty_string_returns_none(self):
        self.assertIsNone(gl.parse_z(""))

    def test_none_returns_none(self):
        self.assertIsNone(gl.parse_z(None))  # type: ignore

    def test_invalid_string_returns_none(self):
        self.assertIsNone(gl.parse_z("not-a-date"))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(gl.parse_z("   "))

    def test_naive_datetime_gets_utc_attached(self):
        # A naive ISO string (no tz) → gets UTC attached
        result = gl.parse_z("2026-01-01T00:00:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, dt.timezone.utc)

    def test_z_and_offset_equivalent(self):
        r1 = gl.parse_z("2026-06-01T10:30:00Z")
        r2 = gl.parse_z("2026-06-01T10:30:00+00:00")
        self.assertEqual(r1, r2)


class TestUtcStamp(unittest.TestCase):
    """Tests for utc_stamp() — ISO timestamp with Z suffix."""

    def test_ends_with_z(self):
        stamp = gl.utc_stamp()
        self.assertTrue(stamp.endswith("Z"), f"Expected Z suffix: {stamp!r}")

    def test_is_parseable(self):
        stamp = gl.utc_stamp()
        result = gl.parse_z(stamp)
        self.assertIsNotNone(result)

    def test_no_microseconds(self):
        stamp = gl.utc_stamp()
        # No "." in the time portion → no microseconds
        time_part = stamp.split("T")[1].rstrip("Z")
        self.assertNotIn(".", time_part)

    def test_looks_like_iso(self):
        stamp = gl.utc_stamp()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestIsExpired(unittest.TestCase):
    """Tests for is_expired() — TTL expiry check."""

    def _future_stamp(self, minutes=60):
        future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
        return future.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _past_stamp(self, minutes=60):
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)
        return past.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def test_none_lock_returns_false(self):
        self.assertFalse(gl.is_expired(None))

    def test_empty_dict_returns_false(self):
        self.assertFalse(gl.is_expired({}))

    def test_future_ttl_not_expired(self):
        lock = {"ttl_until": self._future_stamp()}
        self.assertFalse(gl.is_expired(lock))

    def test_past_ttl_expired(self):
        lock = {"ttl_until": self._past_stamp()}
        self.assertTrue(gl.is_expired(lock))

    def test_missing_ttl_returns_false(self):
        # No "ttl_until" key → parse_z("") → None → expired=False
        lock = {"holder": "coder"}
        self.assertFalse(gl.is_expired(lock))

    def test_invalid_ttl_returns_false(self):
        # Invalid timestamp → parse_z returns None → expired=False
        lock = {"ttl_until": "not-a-date"}
        self.assertFalse(gl.is_expired(lock))


class TestSaveLockLoadLock(unittest.TestCase):
    """Tests for save_lock() / load_lock() — file persistence."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_state = gl.STATE
        self._orig_lock = gl.LOCK
        gl.STATE = str(self._tmp / "state")
        gl.LOCK = str(self._tmp / "state" / "lock.json")

    def tearDown(self):
        gl.STATE = self._orig_state
        gl.LOCK = self._orig_lock
        self._tmpdir.cleanup()

    def test_load_lock_missing_file_returns_none(self):
        result = gl.load_lock()
        self.assertIsNone(result)

    def test_save_and_load_round_trip(self):
        payload = {"holder": "coder", "reason": "test", "ts": "2026-01-01T00:00:00Z"}
        gl.save_lock(payload)
        result = gl.load_lock()
        self.assertEqual(result["holder"], "coder")
        self.assertEqual(result["reason"], "test")

    def test_save_creates_directory(self):
        state_dir = Path(gl.STATE)
        self.assertFalse(state_dir.exists())
        gl.save_lock({"test": True})
        self.assertTrue(state_dir.exists())

    def test_load_invalid_json_returns_none(self):
        state_dir = Path(gl.STATE)
        state_dir.mkdir(parents=True, exist_ok=True)
        Path(gl.LOCK).write_text("not json!", encoding="utf-8")
        result = gl.load_lock()
        self.assertIsNone(result)

    def test_load_non_dict_json_returns_none(self):
        state_dir = Path(gl.STATE)
        state_dir.mkdir(parents=True, exist_ok=True)
        Path(gl.LOCK).write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        result = gl.load_lock()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
