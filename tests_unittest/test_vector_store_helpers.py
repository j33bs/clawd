"""Tests for pure helpers in workspace/knowledge_base/vector_store_lancedb.py.

Stubs lancedb and pyarrow to allow clean module load.
Covers stdlib-only pure functions:
- make_row_id
- _escape_sql
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "workspace" / "knowledge_base"

# Stub lancedb and pyarrow before loading
if "lancedb" not in sys.modules:
    sys.modules["lancedb"] = types.ModuleType("lancedb")

if "pyarrow" not in sys.modules:
    _pa = types.ModuleType("pyarrow")
    _pa.Schema = object
    _pa.field = lambda *a, **kw: None
    _pa.schema = lambda *a, **kw: None
    _pa.list_ = lambda *a, **kw: None
    _pa.float32 = lambda: None
    _pa.utf8 = lambda: None
    _pa.int64 = lambda: None
    sys.modules["pyarrow"] = _pa
else:
    _pa = sys.modules["pyarrow"]
    for attr in ("field", "schema", "list_", "float32", "utf8", "int64"):
        if not hasattr(_pa, attr):
            setattr(_pa, attr, lambda *a, **kw: None)

_spec = _ilu.spec_from_file_location(
    "vector_store_lancedb_mod",
    str(KB_DIR / "vector_store_lancedb.py"),
)
_vsdb = _ilu.module_from_spec(_spec)
sys.modules["vector_store_lancedb_mod"] = _vsdb
_spec.loader.exec_module(_vsdb)

make_row_id = _vsdb.make_row_id
_escape_sql = _vsdb._escape_sql


# ---------------------------------------------------------------------------
# make_row_id
# ---------------------------------------------------------------------------

class TestMakeRowId(unittest.TestCase):
    """Tests for make_row_id() — deterministic SHA-256 row ID."""

    def test_returns_string(self):
        result = make_row_id("doc1", "chunk1", "model1")
        self.assertIsInstance(result, str)

    def test_fixed_length_32(self):
        result = make_row_id("doc1", "chunk1", "model1")
        self.assertEqual(len(result), 32)

    def test_deterministic(self):
        a = make_row_id("docA", "chunkB", "modelC")
        b = make_row_id("docA", "chunkB", "modelC")
        self.assertEqual(a, b)

    def test_different_inputs_differ(self):
        a = make_row_id("doc1", "chunk1", "model1")
        b = make_row_id("doc2", "chunk1", "model1")
        self.assertNotEqual(a, b)

    def test_hex_string(self):
        result = make_row_id("x", "y", "z")
        int(result, 16)  # must not raise

    def test_all_empty_strings(self):
        result = make_row_id("", "", "")
        self.assertEqual(len(result), 32)


# ---------------------------------------------------------------------------
# _escape_sql
# ---------------------------------------------------------------------------

class TestEscapeSql(unittest.TestCase):
    """Tests for _escape_sql() — escape single quotes for SQL WHERE clauses."""

    def test_no_quotes_unchanged(self):
        self.assertEqual(_escape_sql("hello world"), "hello world")

    def test_single_quote_doubled(self):
        self.assertEqual(_escape_sql("it's"), "it''s")

    def test_multiple_quotes(self):
        result = _escape_sql("it's a dog's life")
        self.assertEqual(result, "it''s a dog''s life")

    def test_empty_string(self):
        self.assertEqual(_escape_sql(""), "")

    def test_returns_string(self):
        self.assertIsInstance(_escape_sql("test"), str)

    def test_non_string_coerced(self):
        result = _escape_sql(123)
        self.assertEqual(result, "123")


if __name__ == "__main__":
    unittest.main()
