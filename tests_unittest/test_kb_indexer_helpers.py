"""Tests for pure helpers in workspace/knowledge_base/indexer.py.

Stubs chunking, embeddings.driver_mlx, and vector_store_lancedb
(with make_row_id) to avoid heavy deps.

Covers:
- _utc_now_iso
- _repo_root
- _default_db_dir
- _meta_path
- _load_meta
- _save_meta
- _hash_text
- _read_text
- _relative_doc_id
"""
import hashlib
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "workspace" / "knowledge_base"

# ---------------------------------------------------------------------------
# Stubs — must be in sys.modules before importing indexer
# ---------------------------------------------------------------------------

# chunking stub
if "chunking" not in sys.modules:
    _chunking_stub = types.ModuleType("chunking")
    _chunking_stub.chunk_markdown = lambda *a, **kw: []
    sys.modules["chunking"] = _chunking_stub

# embeddings stubs (may already be set by other test files)
if "embeddings" not in sys.modules:
    _emb_pkg = types.ModuleType("embeddings")
    _emb_pkg.__path__ = []
    sys.modules["embeddings"] = _emb_pkg

if "embeddings.driver_mlx" not in sys.modules:
    _mlx_mod = types.ModuleType("embeddings.driver_mlx")
    _mlx_mod.ACCEL_MODEL_ID = "accel-model"
    _mlx_mod.CANONICAL_MODEL_ID = "canonical-model"
    _mlx_mod.MlxEmbedder = MagicMock()
    sys.modules["embeddings.driver_mlx"] = _mlx_mod

# vector_store_lancedb stub (may already be set)
if "vector_store_lancedb" not in sys.modules:
    _vsdb_mod = types.ModuleType("vector_store_lancedb")
    _vsdb_mod.MINILM_DIM = 384
    _vsdb_mod.MINILM_TABLE = "rag_minilm"
    _vsdb_mod.MODERNBERT_DIM = 768
    _vsdb_mod.MODERNBERT_TABLE = "rag_modernbert"
    _vsdb_mod.LanceVectorStore = MagicMock()
    _vsdb_mod.make_row_id = MagicMock(return_value="row-id")
    sys.modules["vector_store_lancedb"] = _vsdb_mod
else:
    # Ensure make_row_id exists on existing stub
    if not hasattr(sys.modules["vector_store_lancedb"], "make_row_id"):
        sys.modules["vector_store_lancedb"].make_row_id = MagicMock(return_value="row-id")

# Add KB_DIR to sys.path so chunking.py can be found too
if str(KB_DIR) not in sys.path:
    sys.path.insert(0, str(KB_DIR))

_spec = _ilu.spec_from_file_location(
    "kb_indexer_real",
    str(KB_DIR / "indexer.py"),
)
ix = _ilu.module_from_spec(_spec)
sys.modules["kb_indexer_real"] = ix
_spec.loader.exec_module(ix)


# ---------------------------------------------------------------------------
# _utc_now_iso
# ---------------------------------------------------------------------------

class TestUtcNowIso(unittest.TestCase):
    """Tests for _utc_now_iso() — current UTC time as ISO string."""

    def test_returns_string(self):
        result = ix._utc_now_iso()
        self.assertIsInstance(result, str)

    def test_contains_plus_offset(self):
        # indexer._utc_now_iso uses .isoformat() which gives +00:00 not Z
        result = ix._utc_now_iso()
        self.assertIn("+00:00", result)

    def test_parseable_as_iso(self):
        from datetime import datetime
        result = ix._utc_now_iso()
        # Should parse without error
        datetime.fromisoformat(result)


# ---------------------------------------------------------------------------
# _repo_root
# ---------------------------------------------------------------------------

class TestRepoRoot(unittest.TestCase):
    """Tests for _repo_root() — returns repo root path."""

    def test_env_override_name(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_REPO_ROOT": "/tmp/myrepo"}):
            result = ix._repo_root()
            self.assertEqual(result.name, "myrepo")

    def test_default_is_absolute(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_REPO_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            result = ix._repo_root()
            self.assertTrue(result.is_absolute())

    def test_returns_path(self):
        result = ix._repo_root()
        self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# _default_db_dir
# ---------------------------------------------------------------------------

class TestDefaultDbDir(unittest.TestCase):
    """Tests for _default_db_dir() — returns vector DB directory."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_VECTOR_DB_DIR": "/tmp/vecs"}):
            result = ix._default_db_dir(Path("/repo"))
            self.assertEqual(result.name, "vecs")

    def test_default_contains_vectors_lance(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_VECTOR_DB_DIR"}
        with patch.dict(os.environ, env, clear=True):
            result = ix._default_db_dir(Path("/repo"))
            self.assertIn("vectors.lance", str(result))

    def test_returns_path(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_VECTOR_DB_DIR"}
        with patch.dict(os.environ, env, clear=True):
            result = ix._default_db_dir(Path("/repo"))
            self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# _meta_path
# ---------------------------------------------------------------------------

class TestMetaPath(unittest.TestCase):
    """Tests for _meta_path() — returns embeddings meta JSON path."""

    def test_env_override_used(self):
        with patch.dict(os.environ, {"OPENCLAW_KB_EMBED_META_PATH": "/tmp/meta.json"}):
            result = ix._meta_path(Path("/repo"))
            self.assertEqual(result.name, "meta.json")

    def test_default_contains_embeddings_meta(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_KB_EMBED_META_PATH"}
        with patch.dict(os.environ, env, clear=True):
            result = ix._meta_path(Path("/repo"))
            self.assertIn("embeddings.meta.json", str(result))

    def test_returns_path(self):
        result = ix._meta_path(Path("/repo"))
        self.assertIsInstance(result, Path)


# ---------------------------------------------------------------------------
# _load_meta
# ---------------------------------------------------------------------------

class TestLoadMeta(unittest.TestCase):
    """Tests for _load_meta() — loads JSON meta or returns defaults."""

    def test_missing_file_returns_defaults(self):
        result = ix._load_meta(Path("/nonexistent/meta.json"))
        self.assertIn("version", result)
        self.assertIn("docs", result)

    def test_valid_json_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "meta.json"
            p.write_text(json.dumps({"version": 2, "docs": {"a": {}}}), encoding="utf-8")
            result = ix._load_meta(p)
            self.assertEqual(result["version"], 2)

    def test_invalid_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "meta.json"
            p.write_text("NOT JSON", encoding="utf-8")
            result = ix._load_meta(p)
            self.assertEqual(result["docs"], {})

    def test_returns_dict(self):
        result = ix._load_meta(Path("/no/file"))
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# _save_meta
# ---------------------------------------------------------------------------

class TestSaveMeta(unittest.TestCase):
    """Tests for _save_meta() — writes meta dict to JSON file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "meta.json"
            ix._save_meta(p, {"version": 1, "docs": {}})
            self.assertTrue(p.exists())

    def test_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "meta.json"
            ix._save_meta(p, {"version": 3, "docs": {"x": {}}})
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], 3)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b" / "meta.json"
            ix._save_meta(p, {"version": 1})
            self.assertTrue(p.parent.is_dir())


# ---------------------------------------------------------------------------
# _hash_text
# ---------------------------------------------------------------------------

class TestHashText(unittest.TestCase):
    """Tests for _hash_text() — SHA-256 hex digest of text."""

    def test_known_value(self):
        expected = hashlib.sha256(b"hello").hexdigest()
        self.assertEqual(ix._hash_text("hello"), expected)

    def test_empty_string(self):
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(ix._hash_text(""), expected)

    def test_different_texts_differ(self):
        self.assertNotEqual(ix._hash_text("a"), ix._hash_text("b"))

    def test_returns_64_char_hex(self):
        result = ix._hash_text("test")
        self.assertEqual(len(result), 64)
        int(result, 16)  # should not raise

    def test_deterministic(self):
        self.assertEqual(ix._hash_text("same"), ix._hash_text("same"))


# ---------------------------------------------------------------------------
# _read_text
# ---------------------------------------------------------------------------

class TestReadText(unittest.TestCase):
    """Tests for _read_text() — reads file content as UTF-8 string."""

    def test_reads_file_content(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "doc.md"
            p.write_text("# Hello World\n", encoding="utf-8")
            result = ix._read_text(p)
            self.assertEqual(result, "# Hello World\n")

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.txt"
            p.write_text("x", encoding="utf-8")
            result = ix._read_text(p)
            self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# _relative_doc_id
# ---------------------------------------------------------------------------

class TestRelativeDocId(unittest.TestCase):
    """Tests for _relative_doc_id() — returns posix relative path string."""

    def test_relative_path_returned(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            doc = root / "workspace" / "doc.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.touch()
            result = ix._relative_doc_id(doc, root)
            self.assertEqual(result, "workspace/doc.md")

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            doc = root / "file.md"
            doc.touch()
            result = ix._relative_doc_id(doc, root)
            self.assertIsInstance(result, str)

    def test_uses_posix_separators(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            doc = root / "a" / "b" / "c.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.touch()
            result = ix._relative_doc_id(doc, root)
            self.assertIn("/", result)
            self.assertNotIn("\\", result)


if __name__ == "__main__":
    unittest.main()
