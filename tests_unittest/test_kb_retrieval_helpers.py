"""Tests for pure helpers in workspace/knowledge_base/retrieval.py.

Stubs embeddings.driver_mlx and vector_store_lancedb to avoid heavy deps.
Covers:
- _repo_root
- _default_db_dir
- _doc_filter
- _rows_to_contexts
"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "workspace" / "knowledge_base"

# ---------------------------------------------------------------------------
# Stubs — must be installed before importing retrieval
# ---------------------------------------------------------------------------

_mlx_mod = types.ModuleType("embeddings.driver_mlx")
_mlx_mod.ACCEL_MODEL_ID = "accel-test-model"
_mlx_mod.CANONICAL_MODEL_ID = "canonical-test-model"
_mlx_mod.MlxEmbedder = MagicMock()

_emb_pkg = types.ModuleType("embeddings")
_emb_pkg.__path__ = []

_vsdb_mod = types.ModuleType("vector_store_lancedb")
_vsdb_mod.MINILM_DIM = 384
_vsdb_mod.MINILM_TABLE = "rag_minilm"
_vsdb_mod.MODERNBERT_DIM = 768
_vsdb_mod.MODERNBERT_TABLE = "rag_modernbert"
_vsdb_mod.LanceVectorStore = MagicMock()

sys.modules.setdefault("embeddings", _emb_pkg)
sys.modules.setdefault("embeddings.driver_mlx", _mlx_mod)
sys.modules.setdefault("vector_store_lancedb", _vsdb_mod)

# Load with a unique module name to avoid colliding with any other `retrieval`
# module already in sys.modules from a different test file.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "kb_retrieval_unique",
    str(KB_DIR / "retrieval.py"),
)
_rt_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_rt_mod)
rt = _rt_mod


# ---------------------------------------------------------------------------
# _repo_root
# ---------------------------------------------------------------------------

class TestRepoRoot(unittest.TestCase):
    """Tests for _repo_root() — returns repo root via env override or __file__."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_REPO_ROOT": "/tmp/fake_root"}):
            result = rt._repo_root()
            self.assertTrue(str(result).endswith("fake_root"))

    def test_env_override_is_resolved(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_REPO_ROOT": "/tmp/fake_root"}):
            result = rt._repo_root()
            self.assertIsInstance(result, Path)

    def test_default_path_is_path(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_REPO_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            result = rt._repo_root()
            self.assertIsInstance(result, Path)

    def test_default_is_absolute(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_REPO_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            result = rt._repo_root()
            self.assertTrue(result.is_absolute())


# ---------------------------------------------------------------------------
# _default_db_dir
# ---------------------------------------------------------------------------

class TestDefaultDbDir(unittest.TestCase):
    """Tests for _default_db_dir() — returns vector DB path."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_VECTOR_DB_DIR": "/tmp/vec_db"}):
            result = rt._default_db_dir()
            self.assertTrue(str(result).endswith("vec_db"))

    def test_env_override_is_path(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_VECTOR_DB_DIR": "/tmp/vec_db"}):
            result = rt._default_db_dir()
            self.assertIsInstance(result, Path)

    def test_default_contains_vectors_lance(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_VECTOR_DB_DIR"}
        with patch.dict(os.environ, env, clear=True):
            result = rt._default_db_dir()
            self.assertIn("vectors.lance", str(result))


# ---------------------------------------------------------------------------
# _doc_filter
# ---------------------------------------------------------------------------

class TestDocFilter(unittest.TestCase):
    """Tests for _doc_filter() — builds SQL WHERE clause from doc_ids list."""

    def test_empty_list_returns_none(self):
        result = rt._doc_filter([])
        self.assertIsNone(result)

    def test_single_doc_id(self):
        result = rt._doc_filter(["abc123"])
        self.assertIsNotNone(result)
        self.assertIn("'abc123'", result)

    def test_multiple_doc_ids(self):
        result = rt._doc_filter(["a", "b", "c"])
        self.assertIn("'a'", result)
        self.assertIn("'b'", result)
        self.assertIn("'c'", result)

    def test_in_clause_format(self):
        result = rt._doc_filter(["x", "y"])
        self.assertTrue(result.startswith("doc_id IN ("))

    def test_apostrophe_escaped(self):
        result = rt._doc_filter(["doc's"])
        # single-quote inside doc_id should be escaped to ''
        self.assertIn("doc''s", result)

    def test_falsy_entries_skipped(self):
        result = rt._doc_filter(["", "valid", ""])
        self.assertIn("'valid'", result)
        # only one entry
        self.assertEqual(result.count("'valid'"), 1)

    def test_all_empty_returns_none(self):
        result = rt._doc_filter(["", ""])
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _rows_to_contexts
# ---------------------------------------------------------------------------

class TestRowsToContexts(unittest.TestCase):
    """Tests for _rows_to_contexts() — maps raw row dicts to context dicts."""

    def test_empty_rows_returns_empty_list(self):
        result = rt._rows_to_contexts([])
        self.assertEqual(result, [])

    def test_single_row_mapped(self):
        row = {
            "text": "hello",
            "path": "/some/path",
            "doc_id": "d1",
            "chunk_id": "c1",
            "section": "intro",
            "model_id": "minilm",
            "score": 0.9,
            "distance": 0.1,
        }
        result = rt._rows_to_contexts([row])
        self.assertEqual(len(result), 1)
        ctx = result[0]
        self.assertEqual(ctx["text"], "hello")
        self.assertEqual(ctx["doc_id"], "d1")
        self.assertEqual(ctx["score"], 0.9)
        self.assertEqual(ctx["distance"], 0.1)

    def test_missing_fields_default_to_empty_string(self):
        result = rt._rows_to_contexts([{}])
        self.assertEqual(len(result), 1)
        ctx = result[0]
        self.assertEqual(ctx["text"], "")
        self.assertEqual(ctx["path"], "")
        self.assertEqual(ctx["doc_id"], "")
        self.assertEqual(ctx["chunk_id"], "")
        self.assertEqual(ctx["section"], "")
        self.assertEqual(ctx["model_id"], "")

    def test_missing_score_is_none(self):
        result = rt._rows_to_contexts([{}])
        self.assertIsNone(result[0]["score"])

    def test_missing_distance_is_none(self):
        result = rt._rows_to_contexts([{}])
        self.assertIsNone(result[0]["distance"])

    def test_multiple_rows(self):
        rows = [{"text": f"row{i}", "doc_id": f"d{i}"} for i in range(5)]
        result = rt._rows_to_contexts(rows)
        self.assertEqual(len(result), 5)
        for i, ctx in enumerate(result):
            self.assertEqual(ctx["text"], f"row{i}")

    def test_returns_list_of_dicts(self):
        result = rt._rows_to_contexts([{"text": "x"}])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)

    def test_all_eight_keys_present(self):
        result = rt._rows_to_contexts([{"text": "x"}])
        expected_keys = {"text", "path", "doc_id", "chunk_id", "section", "model_id", "score", "distance"}
        self.assertEqual(set(result[0].keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
