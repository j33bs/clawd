"""Tests for pure module-level helpers in workspace/knowledge_base/graph/store.py.

Stdlib-only, no external deps.

Covers:
- _is_quiesced
- _is_protected_target
- _allow_write
"""
import importlib.util as _ilu
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_GRAPH_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "graph" / "store.py"

_spec = _ilu.spec_from_file_location("kb_graph_store_real", str(KB_GRAPH_PATH))
gs = _ilu.module_from_spec(_spec)
sys.modules["kb_graph_store_real"] = gs
_spec.loader.exec_module(gs)


# ---------------------------------------------------------------------------
# _is_quiesced
# ---------------------------------------------------------------------------

class TestIsQuiesced(unittest.TestCase):
    """Tests for _is_quiesced() — checks OPENCLAW_QUIESCE env var."""

    def test_unset_returns_false(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_QUIESCE"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(gs._is_quiesced())

    def test_set_to_one_returns_true(self):
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}):
            self.assertTrue(gs._is_quiesced())

    def test_set_to_zero_returns_false(self):
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "0"}):
            self.assertFalse(gs._is_quiesced())

    def test_returns_bool(self):
        result = gs._is_quiesced()
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# _is_protected_target
# ---------------------------------------------------------------------------

class TestIsProtectedTarget(unittest.TestCase):
    """Tests for _is_protected_target() — checks if path ends with a protected suffix."""

    def test_protected_entities_path(self):
        path = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "entities.jsonl"
        self.assertTrue(gs._is_protected_target(path))

    def test_protected_memory_md(self):
        path = REPO_ROOT / "workspace" / "memory" / "MEMORY.md"
        self.assertTrue(gs._is_protected_target(path))

    def test_unprotected_path_returns_false(self):
        path = Path("/tmp/some_random_file.txt")
        self.assertFalse(gs._is_protected_target(path))

    def test_protected_last_sync(self):
        path = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "last_sync.txt"
        self.assertTrue(gs._is_protected_target(path))

    def test_returns_bool(self):
        result = gs._is_protected_target(Path("/tmp/test.txt"))
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# _allow_write
# ---------------------------------------------------------------------------

class TestAllowWrite(unittest.TestCase):
    """Tests for _allow_write() — False when quiesced + protected, else True."""

    def test_unprotected_path_always_allowed(self):
        path = Path("/tmp/unprotected_test.txt")
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}):
            self.assertTrue(gs._allow_write(path))

    def test_quiesced_protected_path_not_allowed(self):
        path = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "entities.jsonl"
        with patch.dict(os.environ, {"OPENCLAW_QUIESCE": "1"}):
            self.assertFalse(gs._allow_write(path))

    def test_not_quiesced_protected_path_allowed(self):
        path = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "entities.jsonl"
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_QUIESCE"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(gs._allow_write(path))

    def test_returns_bool(self):
        result = gs._allow_write(Path("/tmp/test.txt"))
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
