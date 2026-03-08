"""Tests for pure helpers in workspace/hivemind/hivemind/stigmergy.py.

All stdlib — no network, no external ML deps.
The tacti_cr.events import is wrapped in try/except so gracefully absent.

Covers:
- _to_dt
- _utc
- StigmergyMap._effective (staticmethod)
- StigmergyMap._read / _write (file I/O via tempfile)
"""
import importlib.util as _ilu
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STIGMERGY_PATH = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "stigmergy.py"

_spec = _ilu.spec_from_file_location("hivemind_stigmergy_real", str(STIGMERGY_PATH))
stg = _ilu.module_from_spec(_spec)
sys.modules["hivemind_stigmergy_real"] = stg
_spec.loader.exec_module(stg)


# ---------------------------------------------------------------------------
# _to_dt
# ---------------------------------------------------------------------------

class TestToDt(unittest.TestCase):
    """Tests for _to_dt() — coerce various values to UTC-aware datetime."""

    def test_utc_datetime_passthrough(self):
        dt = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        result = stg._to_dt(dt)
        self.assertEqual(result, dt)

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2026, 3, 7, 12, 0, 0)
        result = stg._to_dt(dt)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_z_suffix_string_parsed(self):
        result = stg._to_dt("2026-03-07T12:00:00Z")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.hour, 12)

    def test_iso_string_with_offset_parsed(self):
        result = stg._to_dt("2026-03-07T12:00:00+00:00")
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_invalid_string_returns_now(self):
        before = datetime.now(timezone.utc)
        result = stg._to_dt("not-a-date")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_none_handled_via_string_conversion(self):
        # None → str(None) = "None" → fromisoformat fails → returns now
        before = datetime.now(timezone.utc)
        result = stg._to_dt(None)
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_returns_datetime(self):
        self.assertIsInstance(stg._to_dt("2026-03-07T12:00:00Z"), datetime)


# ---------------------------------------------------------------------------
# _utc
# ---------------------------------------------------------------------------

class TestUtc(unittest.TestCase):
    """Tests for _utc() — returns UTC ISO string ending with Z."""

    def test_returns_string(self):
        self.assertIsInstance(stg._utc(), str)

    def test_ends_with_z(self):
        self.assertTrue(stg._utc().endswith("Z"))

    def test_accepts_datetime_arg(self):
        dt = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        result = stg._utc(dt)
        self.assertIn("2026", result)
        self.assertTrue(result.endswith("Z"))

    def test_parseable(self):
        result = stg._utc()
        datetime.fromisoformat(result.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# StigmergyMap._effective (staticmethod)
# ---------------------------------------------------------------------------

class TestStigmergyMapEffective(unittest.TestCase):
    """Tests for StigmergyMap._effective() — decayed intensity at a given time."""

    def _mark(self, intensity=1.0, decay_rate=0.0, hours_ago=0.0):
        ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            "intensity": intensity,
            "decay_rate": decay_rate,
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
        }

    def test_no_decay_returns_full_intensity(self):
        now = datetime.now(timezone.utc)
        mark = self._mark(intensity=1.0, decay_rate=0.0, hours_ago=24.0)
        result = stg.StigmergyMap._effective(mark, now)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_high_decay_reduces_intensity(self):
        now = datetime.now(timezone.utc)
        mark = self._mark(intensity=1.0, decay_rate=10.0, hours_ago=2.0)
        result = stg.StigmergyMap._effective(mark, now)
        # exp(-10 * 2) ≈ 2e-9
        self.assertLess(result, 1e-5)

    def test_fresh_mark_near_original(self):
        now = datetime.now(timezone.utc)
        mark = self._mark(intensity=0.8, decay_rate=0.1, hours_ago=0.0)
        result = stg.StigmergyMap._effective(mark, now)
        self.assertAlmostEqual(result, 0.8, delta=0.01)

    def test_result_non_negative(self):
        now = datetime.now(timezone.utc)
        mark = self._mark(intensity=-5.0, decay_rate=0.1, hours_ago=1.0)
        result = stg.StigmergyMap._effective(mark, now)
        self.assertGreaterEqual(result, 0.0)

    def test_returns_float(self):
        now = datetime.now(timezone.utc)
        mark = self._mark(intensity=1.0, decay_rate=0.1, hours_ago=1.0)
        self.assertIsInstance(stg.StigmergyMap._effective(mark, now), float)


# ---------------------------------------------------------------------------
# StigmergyMap._read / _write
# ---------------------------------------------------------------------------

class TestStigmergyMapReadWrite(unittest.TestCase):
    """Tests for StigmergyMap._read() and _write() — JSON list persistence."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._path = Path(self._tmp.name) / "map.json"
        self._map = stg.StigmergyMap(path=self._path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_empty_when_missing(self):
        result = self._map._read()
        self.assertEqual(result, [])

    def test_write_then_read_roundtrip(self):
        rows = [{"topic": "test", "intensity": 0.5}]
        self._map._write(rows)
        result = self._map._read()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["topic"], "test")

    def test_write_multiple_rows(self):
        rows = [{"a": 1}, {"b": 2}, {"c": 3}]
        self._map._write(rows)
        result = self._map._read()
        self.assertEqual(len(result), 3)

    def test_non_dict_entries_excluded(self):
        # Write valid JSON list but with non-dict entries
        self._path.write_text(json.dumps([{"a": 1}, "not-a-dict", 42]), encoding="utf-8")
        result = self._map._read()
        self.assertEqual(len(result), 1)

    def test_invalid_json_returns_empty(self):
        self._path.write_text("not valid json", encoding="utf-8")
        result = self._map._read()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
