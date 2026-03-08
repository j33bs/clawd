"""Tests for workspace/memory_ext/_common.py pure helpers.

No external deps — stdlib only. Loaded with a unique module name.

Covers:
- repo_root
- runtime_dir
- ensure_parent
- utc_now_iso
- env_enabled
- memory_ext_enabled
- append_jsonl
- read_jsonl
"""
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = _ilu.spec_from_file_location(
    "memory_ext_common_real",
    str(REPO_ROOT / "workspace" / "memory_ext" / "_common.py"),
)
cm = _ilu.module_from_spec(_spec)
sys.modules["memory_ext_common_real"] = cm
_spec.loader.exec_module(cm)


# ---------------------------------------------------------------------------
# repo_root
# ---------------------------------------------------------------------------

class TestRepoRoot(unittest.TestCase):
    """Tests for repo_root() — returns repo root via env or __file__ search."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_ROOT": "/tmp/myrepo"}):
            result = cm.repo_root()
            # /tmp may resolve to /private/tmp on macOS; check name only
            self.assertEqual(result.name, "myrepo")

    def test_default_is_absolute(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            result = cm.repo_root()
            self.assertTrue(result.is_absolute())

    def test_returns_path(self):
        with patch.dict(os.environ, {"OPENCLAW_ROOT": "/tmp/myrepo"}):
            result = cm.repo_root()
            self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# runtime_dir
# ---------------------------------------------------------------------------

class TestRuntimeDir(unittest.TestCase):
    """Tests for runtime_dir(*parts) — joins parts under workspace/state_runtime."""

    def test_no_parts_returns_runtime_root(self):
        with patch.dict(os.environ, {"OPENCLAW_ROOT": "/myrepo"}):
            result = cm.runtime_dir()
            self.assertIn("state_runtime", str(result))

    def test_parts_appended(self):
        with patch.dict(os.environ, {"OPENCLAW_ROOT": "/myrepo"}):
            result = cm.runtime_dir("memory", "files")
            self.assertTrue(str(result).endswith("memory/files"))

    def test_returns_path(self):
        with patch.dict(os.environ, {"OPENCLAW_ROOT": "/myrepo"}):
            result = cm.runtime_dir("a")
            self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# ensure_parent
# ---------------------------------------------------------------------------

class TestEnsureParent(unittest.TestCase):
    """Tests for ensure_parent(path) — creates parent directory."""

    def test_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "file.json"
            cm.ensure_parent(p)
            self.assertTrue(p.parent.is_dir())

    def test_already_exists_ok(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "file.json"
            cm.ensure_parent(p)  # td already exists
            self.assertTrue(Path(td).is_dir())


# ---------------------------------------------------------------------------
# utc_now_iso
# ---------------------------------------------------------------------------

class TestUtcNowIso(unittest.TestCase):
    """Tests for utc_now_iso() — ISO-8601 timestamp with Z suffix."""

    def test_returns_string_ending_with_z(self):
        result = cm.utc_now_iso()
        self.assertTrue(result.endswith("Z"))

    def test_explicit_ts_used(self):
        dt = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
        result = cm.utc_now_iso(dt)
        self.assertIn("2026-03-01", result)
        self.assertTrue(result.endswith("Z"))

    def test_returns_string(self):
        result = cm.utc_now_iso()
        self.assertIsInstance(result, str)

    def test_no_plus_offset(self):
        result = cm.utc_now_iso()
        self.assertNotIn("+00:00", result)


# ---------------------------------------------------------------------------
# env_enabled
# ---------------------------------------------------------------------------

class TestEnvEnabled(unittest.TestCase):
    """Tests for env_enabled(name, default) — bool env var check."""

    def test_one_returns_true(self):
        with patch.dict(os.environ, {"MY_FLAG": "1"}):
            self.assertTrue(cm.env_enabled("MY_FLAG"))

    def test_zero_returns_false(self):
        with patch.dict(os.environ, {"MY_FLAG": "0"}):
            self.assertFalse(cm.env_enabled("MY_FLAG"))

    def test_missing_uses_default_false(self):
        env = {k: v for k, v in os.environ.items() if k != "MY_MISSING_FLAG"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(cm.env_enabled("MY_MISSING_FLAG", "0"))

    def test_missing_uses_default_true(self):
        env = {k: v for k, v in os.environ.items() if k != "MY_MISSING_FLAG"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(cm.env_enabled("MY_MISSING_FLAG", "1"))

    def test_returns_bool(self):
        with patch.dict(os.environ, {"MY_FLAG": "1"}):
            result = cm.env_enabled("MY_FLAG")
            self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# memory_ext_enabled
# ---------------------------------------------------------------------------

class TestMemoryExtEnabled(unittest.TestCase):
    """Tests for memory_ext_enabled() — reads OPENCLAW_MEMORY_EXT."""

    def test_unset_returns_false(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_MEMORY_EXT"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(cm.memory_ext_enabled())

    def test_set_to_one_returns_true(self):
        with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "1"}):
            self.assertTrue(cm.memory_ext_enabled())

    def test_returns_bool(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_MEMORY_EXT"}
        with patch.dict(os.environ, env, clear=True):
            result = cm.memory_ext_enabled()
            self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# append_jsonl
# ---------------------------------------------------------------------------

class TestAppendJsonl(unittest.TestCase):
    """Tests for append_jsonl(path, payload) — appends JSONL row."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            cm.append_jsonl(p, {"key": "val"})
            self.assertTrue(p.exists())

    def test_appends_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            cm.append_jsonl(p, {"n": 42})
            data = json.loads(p.read_text(encoding="utf-8").strip())
            self.assertEqual(data["n"], 42)

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            cm.append_jsonl(p, {"n": 1})
            cm.append_jsonl(p, {"n": 2})
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# read_jsonl
# ---------------------------------------------------------------------------

class TestReadJsonl(unittest.TestCase):
    """Tests for read_jsonl(path) — reads JSONL file into list of dicts."""

    def test_missing_file_returns_empty(self):
        result = cm.read_jsonl(Path("/nonexistent/data.jsonl"))
        self.assertEqual(result, [])

    def test_valid_jsonl_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text(json.dumps({"k": "v"}) + "\n", encoding="utf-8")
            result = cm.read_jsonl(p)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["k"], "v")

    def test_multiple_lines(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text(
                json.dumps({"n": 1}) + "\n" + json.dumps({"n": 2}) + "\n",
                encoding="utf-8",
            )
            result = cm.read_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_returns_list(self):
        result = cm.read_jsonl(Path("/no/file"))
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
