"""Tests for pure helpers in workspace/tacti/events_paths.py.

Pure stdlib (os, pathlib) — no stubs needed.
Uses tempfile and env var patching for isolation.

Covers:
- resolve_events_path() — env var override, default fallback
- ensure_parent() — mkdir -p on parent directory
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.tacti.events_paths import resolve_events_path, ensure_parent


# ---------------------------------------------------------------------------
# resolve_events_path
# ---------------------------------------------------------------------------

class TestResolveEventsPath(unittest.TestCase):
    """Tests for resolve_events_path() — env-var override + default path."""

    def test_returns_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_events_path(Path(tmp))
        self.assertIsInstance(result, Path)

    def test_default_path_contains_events_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_events_path(Path(tmp))
        self.assertEqual(result.name, "events.jsonl")

    def test_default_path_under_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = resolve_events_path(root)
        # default is under repo_root/workspace/state_runtime/tacti_cr/
        self.assertTrue(str(result).startswith(str(root)))

    def test_env_var_absolute_path_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom = str(Path(tmp) / "custom" / "events.jsonl")
            with patch.dict(os.environ, {"TACTI_CR_EVENTS_PATH": custom}):
                result = resolve_events_path(Path(tmp))
        self.assertEqual(str(result), custom)

    def test_env_var_relative_path_resolved_against_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(os.environ, {"TACTI_CR_EVENTS_PATH": "data/events.jsonl"}):
                result = resolve_events_path(root)
        self.assertEqual(result, root / "data" / "events.jsonl")

    def test_empty_env_var_uses_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"TACTI_CR_EVENTS_PATH": ""}):
                result = resolve_events_path(Path(tmp))
        self.assertEqual(result.name, "events.jsonl")

    def test_whitespace_env_var_uses_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"TACTI_CR_EVENTS_PATH": "   "}):
                result = resolve_events_path(Path(tmp))
        self.assertEqual(result.name, "events.jsonl")

    def test_env_var_cleared_uses_default(self):
        env = {k: v for k, v in os.environ.items() if k != "TACTI_CR_EVENTS_PATH"}
        with patch.dict(os.environ, env, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                result = resolve_events_path(Path(tmp))
        self.assertEqual(result.name, "events.jsonl")


# ---------------------------------------------------------------------------
# ensure_parent
# ---------------------------------------------------------------------------

class TestEnsureParent(unittest.TestCase):
    """Tests for ensure_parent() — creates parent directory tree."""

    def test_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b" / "c" / "events.jsonl"
            ensure_parent(target)
            self.assertTrue(target.parent.exists())

    def test_idempotent_when_parent_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "events.jsonl"
            ensure_parent(target)  # parent = tmp (already exists)
            ensure_parent(target)  # should not raise
            self.assertTrue(target.parent.exists())

    def test_does_not_create_file_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "events.jsonl"
            ensure_parent(target)
            self.assertFalse(target.exists())
            self.assertTrue(target.parent.exists())

    def test_works_with_string_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "x" / "y" / "f.txt")
            ensure_parent(target)  # accepts string
            self.assertTrue(Path(target).parent.exists())


if __name__ == "__main__":
    unittest.main()
