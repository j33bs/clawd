"""Tests for workspace/memory_ext/_common.py pure helper functions.

Covers:
- utc_now_iso
- env_enabled
- memory_ext_enabled
- runtime_dir
- ensure_parent
- append_jsonl
- read_jsonl
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_EXT_DIR = REPO_ROOT / "workspace" / "memory_ext"
if str(MEMORY_EXT_DIR) not in sys.path:
    sys.path.insert(0, str(MEMORY_EXT_DIR))

from _common import (  # noqa: E402
    append_jsonl,
    env_enabled,
    ensure_parent,
    memory_ext_enabled,
    read_jsonl,
    runtime_dir,
    utc_now_iso,
)


# ---------------------------------------------------------------------------
# utc_now_iso
# ---------------------------------------------------------------------------

class TestUtcNowIso(unittest.TestCase):
    """Tests for utc_now_iso() — ISO timestamp helper."""

    def test_returns_string(self):
        self.assertIsInstance(utc_now_iso(), str)

    def test_ends_with_z(self):
        self.assertTrue(utc_now_iso().endswith("Z"))

    def test_contains_t_separator(self):
        self.assertIn("T", utc_now_iso())

    def test_no_microseconds(self):
        # isoformat strips microseconds via replace(microsecond=0)
        result = utc_now_iso()
        # microseconds would appear after the seconds field as .XXXXXX
        self.assertNotIn(".", result)

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 1, 15, 12, 0, 0)
        result = utc_now_iso(ts=naive)
        self.assertTrue(result.endswith("Z"))
        self.assertIn("2026-01-15T12:00:00", result)

    def test_aware_datetime_converted(self):
        # A datetime with a non-UTC offset should be converted to UTC and get Z suffix
        tz_plus5 = timezone(timedelta(hours=5))
        aware = datetime(2026, 1, 15, 17, 0, 0, tzinfo=tz_plus5)  # 17:00+05 = 12:00 UTC
        result = utc_now_iso(ts=aware)
        self.assertTrue(result.endswith("Z"))
        self.assertIn("2026-01-15T12:00:00", result)

    def test_no_plus00_offset_string(self):
        result = utc_now_iso()
        self.assertNotIn("+00:00", result)


# ---------------------------------------------------------------------------
# env_enabled
# ---------------------------------------------------------------------------

class TestEnvEnabled(unittest.TestCase):
    """Tests for env_enabled() — truthy env var check."""

    def _set(self, name: str, value: str):
        return patch.dict(os.environ, {name: value})

    def test_1_is_true(self):
        with self._set("_TEST_FLAG", "1"):
            self.assertTrue(env_enabled("_TEST_FLAG"))

    def test_true_is_true(self):
        with self._set("_TEST_FLAG", "true"):
            self.assertTrue(env_enabled("_TEST_FLAG"))

    def test_yes_is_true(self):
        with self._set("_TEST_FLAG", "yes"):
            self.assertTrue(env_enabled("_TEST_FLAG"))

    def test_on_is_true(self):
        with self._set("_TEST_FLAG", "on"):
            self.assertTrue(env_enabled("_TEST_FLAG"))

    def test_0_is_false(self):
        with self._set("_TEST_FLAG", "0"):
            self.assertFalse(env_enabled("_TEST_FLAG"))

    def test_false_is_false(self):
        with self._set("_TEST_FLAG", "false"):
            self.assertFalse(env_enabled("_TEST_FLAG"))

    def test_missing_uses_default_0(self):
        env = {k: v for k, v in os.environ.items() if k != "_TEST_FLAG_MISSING"}
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(env_enabled("_TEST_FLAG_MISSING", "0"))

    def test_missing_with_default_1(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(env_enabled("_TEST_FLAG_MISSING", "1"))

    def test_returns_bool(self):
        with self._set("_TEST_FLAG", "1"):
            self.assertIsInstance(env_enabled("_TEST_FLAG"), bool)

    def test_whitespace_stripped(self):
        with self._set("_TEST_FLAG", "  1  "):
            self.assertTrue(env_enabled("_TEST_FLAG"))


# ---------------------------------------------------------------------------
# memory_ext_enabled
# ---------------------------------------------------------------------------

class TestMemoryExtEnabled(unittest.TestCase):
    """Tests for memory_ext_enabled() — OPENCLAW_MEMORY_EXT flag."""

    def test_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(memory_ext_enabled())

    def test_enabled_when_set_1(self):
        with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "1"}):
            self.assertTrue(memory_ext_enabled())

    def test_disabled_when_set_0(self):
        with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}):
            self.assertFalse(memory_ext_enabled())

    def test_returns_bool(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(memory_ext_enabled(), bool)


# ---------------------------------------------------------------------------
# runtime_dir
# ---------------------------------------------------------------------------

class TestRuntimeDir(unittest.TestCase):
    """Tests for runtime_dir() — path under workspace/state_runtime."""

    def test_no_parts_returns_state_runtime(self):
        result = runtime_dir()
        self.assertTrue(str(result).endswith("state_runtime"))

    def test_one_part_appended(self):
        result = runtime_dir("teamchat")
        self.assertTrue(str(result).endswith(os.path.join("state_runtime", "teamchat")))

    def test_multiple_parts_appended_in_order(self):
        result = runtime_dir("a", "b", "c")
        s = str(result)
        self.assertIn("state_runtime", s)
        # a/b/c must appear in order
        idx_a = s.rfind("a")
        idx_b = s.rfind("b")
        idx_c = s.rfind("c")
        self.assertLess(idx_a, idx_b)
        self.assertLess(idx_b, idx_c)

    def test_returns_path(self):
        self.assertIsInstance(runtime_dir(), Path)


# ---------------------------------------------------------------------------
# ensure_parent
# ---------------------------------------------------------------------------

class TestEnsureParent(unittest.TestCase):
    """Tests for ensure_parent() — mkdir for parent directory."""

    def test_creates_parent(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "deep" / "nested" / "file.txt"
            ensure_parent(target)
            self.assertTrue(target.parent.exists())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "sub" / "file.txt"
            ensure_parent(target)
            ensure_parent(target)  # should not raise
            self.assertTrue(target.parent.exists())

    def test_existing_parent_ok(self):
        with tempfile.TemporaryDirectory() as td:
            # parent already exists
            target = Path(td) / "file.txt"
            ensure_parent(target)  # td is already a directory
            self.assertTrue(target.parent.exists())


# ---------------------------------------------------------------------------
# append_jsonl
# ---------------------------------------------------------------------------

class TestAppendJsonl(unittest.TestCase):
    """Tests for append_jsonl() — JSONL writer with sorted keys."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"key": "value"})
            self.assertTrue(p.exists())

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "deep" / "nested" / "log.jsonl"
            append_jsonl(p, {"key": "value"})
            self.assertTrue(p.exists())

    def test_appends_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"event": "test", "value": 42})
            line = p.read_text(encoding="utf-8").strip()
            parsed = json.loads(line)
            self.assertEqual(parsed["event"], "test")
            self.assertEqual(parsed["value"], 42)

    def test_keys_sorted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"z_key": 1, "a_key": 2, "m_key": 3})
            line = p.read_text(encoding="utf-8").strip()
            # In sorted JSON, a_key should appear before m_key before z_key
            idx_a = line.index("a_key")
            idx_m = line.index("m_key")
            idx_z = line.index("z_key")
            self.assertLess(idx_a, idx_m)
            self.assertLess(idx_m, idx_z)

    def test_multiple_appends_produce_multiple_lines(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"n": 1})
            append_jsonl(p, {"n": 2})
            append_jsonl(p, {"n": 3})
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 3)

    def test_each_line_is_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.jsonl"
            append_jsonl(p, {"x": 1})
            append_jsonl(p, {"x": 2})
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    obj = json.loads(line)
                    self.assertIsInstance(obj, dict)


# ---------------------------------------------------------------------------
# read_jsonl
# ---------------------------------------------------------------------------

class TestReadJsonl(unittest.TestCase):
    """Tests for read_jsonl() — JSONL reader."""

    def test_missing_file_returns_empty(self):
        result = read_jsonl(Path("/nonexistent/totally/missing.jsonl"))
        self.assertEqual(result, [])

    def test_valid_lines_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_invalid_json_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('not json\n{"b": 2}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 1)

    def test_non_dict_json_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('["list"]\n{"ok": true}\n', encoding="utf-8")
            result = read_jsonl(p)
            self.assertEqual(len(result), 1)

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"x": 1}\n', encoding="utf-8")
            self.assertIsInstance(read_jsonl(p), list)

    def test_values_are_dicts(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"x": 1}\n{"y": 2}\n', encoding="utf-8")
            result = read_jsonl(p)
            for row in result:
                self.assertIsInstance(row, dict)


if __name__ == "__main__":
    unittest.main()
