"""Tests for pure helpers in workspace/knowledge_base/vector_store_lancedb.py.

Stubs lancedb and pyarrow (not available in system python3.11).

Covers:
- make_row_id(doc_id, chunk_id, model_id) — SHA-256 hash, first 32 hex chars
- _escape_sql(value) — single-quote escaping for SQL
- Module-level constants (MODERNBERT_TABLE, MINILM_TABLE, etc.)
"""
import hashlib
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "vector_store_lancedb.py"


def _ensure_stubs():
    """Stub lancedb and pyarrow if not available."""
    try:
        import lancedb  # noqa: F401
        return
    except ImportError:
        pass

    ldb = types.ModuleType("lancedb")
    ldb.connect = lambda *a, **k: None
    sys.modules["lancedb"] = ldb

    pa = types.ModuleType("pyarrow")
    pa.schema = lambda fields: None
    pa.field = lambda name, typ: None
    pa.string = lambda: "str"
    pa.int32 = lambda: "int32"
    pa.float32 = lambda: "float32"
    pa.list_ = lambda typ, size=None: f"list<{typ}>"
    sys.modules["pyarrow"] = pa


_ensure_stubs()

_spec = _ilu.spec_from_file_location("vector_store_lancedb_real", str(MODULE_PATH))
vsdb = _ilu.module_from_spec(_spec)
sys.modules["vector_store_lancedb_real"] = vsdb
_spec.loader.exec_module(vsdb)

make_row_id = vsdb.make_row_id
_escape_sql = vsdb._escape_sql


# ---------------------------------------------------------------------------
# make_row_id
# ---------------------------------------------------------------------------


class TestMakeRowId(unittest.TestCase):
    """Tests for make_row_id() — deterministic SHA-256 row ID."""

    def test_returns_string(self):
        self.assertIsInstance(make_row_id("doc", "chunk", "model"), str)

    def test_length_is_32(self):
        self.assertEqual(len(make_row_id("doc", "chunk", "model")), 32)

    def test_all_hex_chars(self):
        result = make_row_id("doc", "chunk", "model")
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_deterministic(self):
        r1 = make_row_id("docA", "c1", "minilm")
        r2 = make_row_id("docA", "c1", "minilm")
        self.assertEqual(r1, r2)

    def test_different_doc_id_gives_different_result(self):
        r1 = make_row_id("docA", "c1", "minilm")
        r2 = make_row_id("docB", "c1", "minilm")
        self.assertNotEqual(r1, r2)

    def test_different_chunk_id_gives_different_result(self):
        r1 = make_row_id("docA", "c1", "minilm")
        r2 = make_row_id("docA", "c2", "minilm")
        self.assertNotEqual(r1, r2)

    def test_different_model_id_gives_different_result(self):
        r1 = make_row_id("docA", "c1", "minilm")
        r2 = make_row_id("docA", "c1", "modernbert")
        self.assertNotEqual(r1, r2)

    def test_matches_manual_sha256(self):
        payload = "docA:chunk1:minilm".encode("utf-8")
        expected = hashlib.sha256(payload).hexdigest()[:32]
        self.assertEqual(make_row_id("docA", "chunk1", "minilm"), expected)

    def test_empty_strings(self):
        result = make_row_id("", "", "")
        self.assertEqual(len(result), 32)

    def test_colon_separation_matters(self):
        # "a:b:c" != "ab::c" != "a::bc"
        r1 = make_row_id("a", "b", "c")
        r2 = make_row_id("ab", "", "c")
        self.assertNotEqual(r1, r2)


# ---------------------------------------------------------------------------
# _escape_sql
# ---------------------------------------------------------------------------


class TestEscapeSql(unittest.TestCase):
    """Tests for _escape_sql() — escapes single quotes for SQL safety."""

    def test_no_quotes_unchanged(self):
        self.assertEqual(_escape_sql("hello world"), "hello world")

    def test_single_quote_doubled(self):
        self.assertEqual(_escape_sql("it's"), "it''s")

    def test_multiple_quotes_all_doubled(self):
        self.assertEqual(_escape_sql("'quoted'"), "''quoted''")

    def test_empty_string(self):
        self.assertEqual(_escape_sql(""), "")

    def test_non_string_int_converted(self):
        result = _escape_sql(42)
        self.assertEqual(result, "42")

    def test_non_string_path_converted(self):
        result = _escape_sql(Path("/some/path"))
        self.assertIsInstance(result, str)

    def test_consecutive_quotes(self):
        self.assertEqual(_escape_sql("''"), "''''")

    def test_returns_string(self):
        self.assertIsInstance(_escape_sql("test"), str)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestModuleConstants(unittest.TestCase):
    """Tests for module-level constants."""

    def test_modernbert_table_name(self):
        self.assertEqual(vsdb.MODERNBERT_TABLE, "rag_modernbert")

    def test_minilm_table_name(self):
        self.assertEqual(vsdb.MINILM_TABLE, "rag_minilm")

    def test_modernbert_dim(self):
        self.assertEqual(vsdb.MODERNBERT_DIM, 768)

    def test_minilm_dim(self):
        self.assertEqual(vsdb.MINILM_DIM, 384)


if __name__ == "__main__":
    unittest.main()
