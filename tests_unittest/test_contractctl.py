"""Tests for contractctl — parse_duration, load_json, save_json."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import contractctl


class TestParseDuration(unittest.TestCase):
    """Tests for parse_duration() — human-readable duration string to timedelta."""

    def test_hours_parsed(self):
        td = contractctl.parse_duration("2h")
        self.assertEqual(td.total_seconds(), 2 * 3600)

    def test_minutes_parsed(self):
        td = contractctl.parse_duration("30m")
        self.assertEqual(td.total_seconds(), 30 * 60)

    def test_hours_and_minutes_combined(self):
        td = contractctl.parse_duration("1h30m")
        self.assertEqual(td.total_seconds(), 1.5 * 3600)

    def test_multiple_hours_and_minutes(self):
        td = contractctl.parse_duration("2h45m")
        self.assertEqual(td.total_seconds(), 2 * 3600 + 45 * 60)

    def test_case_insensitive(self):
        td = contractctl.parse_duration("1H")
        self.assertEqual(td.total_seconds(), 3600)

    def test_whitespace_stripped(self):
        td = contractctl.parse_duration("  1h  ")
        self.assertEqual(td.total_seconds(), 3600)

    def test_zero_duration_raises(self):
        with self.assertRaises(ValueError):
            contractctl.parse_duration("0h0m")

    def test_invalid_string_raises(self):
        with self.assertRaises(ValueError):
            contractctl.parse_duration("not-a-duration")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            contractctl.parse_duration("")

    def test_only_digits_raises(self):
        with self.assertRaises(ValueError):
            contractctl.parse_duration("120")

    def test_large_hours(self):
        td = contractctl.parse_duration("24h")
        self.assertEqual(td.total_seconds(), 24 * 3600)

    def test_ordering_hours_then_minutes(self):
        td1 = contractctl.parse_duration("1h30m")
        td2 = contractctl.parse_duration("30m1h")
        self.assertEqual(td1, td2)


class TestLoadJson(unittest.TestCase):
    """Tests for load_json() — file loading with fallback default."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_default(self):
        result = contractctl.load_json(str(self._tmp / "nonexistent.json"), {"default": True})
        self.assertEqual(result, {"default": True})

    def test_valid_json_loaded(self):
        path = self._tmp / "data.json"
        path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = contractctl.load_json(str(path), {})
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json_returns_default(self):
        path = self._tmp / "bad.json"
        path.write_text("not json!", encoding="utf-8")
        result = contractctl.load_json(str(path), {"fallback": 1})
        self.assertEqual(result, {"fallback": 1})

    def test_list_default_used_when_missing(self):
        result = contractctl.load_json(str(self._tmp / "missing.json"), [])
        self.assertEqual(result, [])

    def test_loaded_data_overrides_default(self):
        path = self._tmp / "override.json"
        path.write_text(json.dumps({"real": "data"}), encoding="utf-8")
        result = contractctl.load_json(str(path), {"default": "value"})
        self.assertEqual(result["real"], "data")
        self.assertNotIn("default", result)


class TestSaveJson(unittest.TestCase):
    """Tests for save_json() — atomic write with tmp swap."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_creates_file(self):
        path = self._tmp / "out.json"
        contractctl.save_json(str(path), {"k": "v"})
        self.assertTrue(path.exists())

    def test_creates_parent_dirs(self):
        path = self._tmp / "nested" / "dir" / "out.json"
        contractctl.save_json(str(path), {"a": 1})
        self.assertTrue(path.exists())

    def test_file_is_valid_json(self):
        path = self._tmp / "data.json"
        contractctl.save_json(str(path), {"x": 42})
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["x"], 42)

    def test_ends_with_newline(self):
        path = self._tmp / "nl.json"
        contractctl.save_json(str(path), {"n": 1})
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))

    def test_keys_sorted(self):
        path = self._tmp / "sorted.json"
        contractctl.save_json(str(path), {"z": 1, "a": 2, "m": 3})
        content = path.read_text(encoding="utf-8")
        # In sorted JSON, "a" comes before "m" which comes before "z"
        a_pos = content.index('"a"')
        m_pos = content.index('"m"')
        z_pos = content.index('"z"')
        self.assertLess(a_pos, m_pos)
        self.assertLess(m_pos, z_pos)

    def test_overwrites_existing(self):
        path = self._tmp / "overwrite.json"
        contractctl.save_json(str(path), {"v": 1})
        contractctl.save_json(str(path), {"v": 2})
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["v"], 2)

    def test_no_tmp_file_left_behind(self):
        path = self._tmp / "clean.json"
        contractctl.save_json(str(path), {"ok": True})
        tmp_path = Path(str(path) + ".tmp")
        self.assertFalse(tmp_path.exists())


if __name__ == "__main__":
    unittest.main()
