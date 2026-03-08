import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "telegram_vector_store.py"


def load_module():
    script_dir = str(MODULE_PATH.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("telegram_vector_store", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TelegramVectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def _write_normalized(self, path: Path) -> None:
        rows = [
            {
                "hash": "hash-a",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "1",
                "timestamp": "2026-02-20T10:00:00Z",
                "sender_name": "jeebs",
                "text": "We discussed phase eleven enhancements for telegram memory recall.",
                "reply_to_message_id": None,
            },
            {
                "hash": "hash-b",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "2",
                "timestamp": "2026-02-20T10:01:00Z",
                "sender_name": "c_lawd",
                "text": "Vector store should support semantic search and context loading.",
                "reply_to_message_id": "1",
            },
            {
                "hash": "hash-b",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "2",
                "timestamp": "2026-02-20T10:01:00Z",
                "sender_name": "c_lawd",
                "text": "Vector store should support semantic search and context loading.",
                "reply_to_message_id": "1",
            },
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    def test_build_dedup_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            normalized = root / "normalized.jsonl"
            store_dir = root / "store"
            self._write_normalized(normalized)

            first = self.mod.build_store(
                normalized_path=normalized,
                store_dir=store_dir,
                embedder_name="keyword_stub",
                force_backend="jsonl",
            )
            second = self.mod.build_store(
                normalized_path=normalized,
                store_dir=store_dir,
                embedder_name="keyword_stub",
                force_backend="jsonl",
            )

            self.assertEqual(first["count"], 2)
            self.assertEqual(first["inserted"], 2)
            self.assertEqual(second["count"], 2)
            self.assertEqual(second["inserted"], 0)

    def test_query_returns_expected_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            normalized = root / "normalized.jsonl"
            store_dir = root / "store"
            self._write_normalized(normalized)

            self.mod.build_store(
                normalized_path=normalized,
                store_dir=store_dir,
                embedder_name="keyword_stub",
                force_backend="jsonl",
            )

            results = self.mod.search_store(
                "phase eleven enhancements recall",
                topk=2,
                store_dir=store_dir,
            )
            self.assertGreaterEqual(len(results), 1)
            self.assertIn("phase eleven enhancements", results[0]["text"].lower())


class TestLoadJsonl(unittest.TestCase):
    """Tests for telegram_vector_store.load_jsonl()."""

    def setUp(self):
        self.mod = load_module()

    def test_missing_file_returns_empty(self):
        result = self.mod.load_jsonl(Path("/nonexistent/path/xyz.jsonl"))
        self.assertEqual(result, [])

    def test_valid_jsonl_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"hash":"a","text":"hello"}\n{"hash":"b","text":"world"}\n', encoding="utf-8")
            result = self.mod.load_jsonl(p)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["hash"], "a")

    def test_invalid_json_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"hash":"a"}\nnot json\n{"hash":"b"}\n', encoding="utf-8")
            result = self.mod.load_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"hash":"a"}\n\n   \n{"hash":"b"}\n', encoding="utf-8")
            result = self.mod.load_jsonl(p)
            self.assertEqual(len(result), 2)

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            p.write_text('{"x":1}\n', encoding="utf-8")
            self.assertIsInstance(self.mod.load_jsonl(p), list)


class TestWriteJsonl(unittest.TestCase):
    """Tests for telegram_vector_store.write_jsonl() — sorted JSONL writer."""

    def setUp(self):
        self.mod = load_module()

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "data.jsonl"
            self.mod.write_jsonl(p, [{"hash": "a", "timestamp": "2026-01-01"}])
            self.assertTrue(p.exists())

    def test_sorted_by_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            rows = [
                {"hash": "b", "timestamp": "2026-03-01"},
                {"hash": "a", "timestamp": "2026-01-01"},
            ]
            self.mod.write_jsonl(p, rows)
            import json as _json
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            first = _json.loads(lines[0])
            self.assertEqual(first["hash"], "a")  # earlier timestamp first

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.jsonl"
            rows = [{"hash": "x", "text": "hello"}]
            self.mod.write_jsonl(p, rows)
            result = self.mod.load_jsonl(p)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["hash"], "x")


class TestMetadataIO(unittest.TestCase):
    """Tests for write_metadata() and read_metadata()."""

    def setUp(self):
        self.mod = load_module()

    def test_write_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            store_dir = Path(td) / "store"
            payload = {"backend": "jsonl", "count": 42}
            self.mod.write_metadata(store_dir, payload)
            result = self.mod.read_metadata(store_dir)
            self.assertEqual(result["backend"], "jsonl")
            self.assertEqual(result["count"], 42)

    def test_read_metadata_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.mod.read_metadata(Path(td) / "nonexistent")
            self.assertEqual(result, {})

    def test_read_metadata_invalid_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            store_dir = Path(td)
            meta_path = self.mod.metadata_path(store_dir)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text("not json", encoding="utf-8")
            result = self.mod.read_metadata(store_dir)
            self.assertEqual(result, {})


class TestPathHelpers(unittest.TestCase):
    """Tests for records_path() and metadata_path()."""

    def setUp(self):
        self.mod = load_module()

    def test_records_path_returns_path_in_store_dir(self):
        store_dir = Path("/tmp/mystore")
        result = self.mod.records_path(store_dir)
        self.assertIsInstance(result, Path)
        self.assertEqual(result.parent, store_dir)
        self.assertTrue(result.name.endswith(".jsonl"))

    def test_metadata_path_returns_json(self):
        store_dir = Path("/tmp/mystore")
        result = self.mod.metadata_path(store_dir)
        self.assertEqual(result.parent, store_dir)
        self.assertEqual(result.suffix, ".json")


class TestToStoreRecord(unittest.TestCase):
    """Tests for to_store_record() — row + embedding -> store dict."""

    def setUp(self):
        self.mod = load_module()

    def test_returns_dict(self):
        row = {"hash": "abc", "chat_id": 123, "text": "hello"}
        result = self.mod.to_store_record(row, [0.1, 0.2])
        self.assertIsInstance(result, dict)

    def test_chat_id_cast_to_str(self):
        row = {"hash": "abc", "chat_id": 999, "text": "hello"}
        result = self.mod.to_store_record(row, [])
        self.assertEqual(result["chat_id"], "999")

    def test_embedding_stored_as_floats(self):
        row = {"hash": "abc"}
        result = self.mod.to_store_record(row, [1, 2, 3])
        self.assertEqual(result["embedding"], [1.0, 2.0, 3.0])

    def test_text_preserved(self):
        row = {"hash": "abc", "text": "my text content"}
        result = self.mod.to_store_record(row, [])
        self.assertEqual(result["text"], "my text content")

    def test_required_keys_present(self):
        row = {"hash": "h1"}
        result = self.mod.to_store_record(row, [])
        for key in ("hash", "chat_id", "chat_title", "message_id", "timestamp",
                    "sender_name", "text", "embedding", "reply_to_message_id"):
            self.assertIn(key, result)

    def test_missing_fields_return_none(self):
        row = {}
        result = self.mod.to_store_record(row, [])
        self.assertIsNone(result["hash"])
        self.assertIsNone(result["text"])


class TestEscapeSql(unittest.TestCase):
    """Tests for _escape_sql() — single-quote doubler."""

    def setUp(self):
        self.mod = load_module()

    def test_no_quotes_passthrough(self):
        self.assertEqual(self.mod._escape_sql("hello world"), "hello world")

    def test_single_quote_doubled(self):
        result = self.mod._escape_sql("it's me")
        self.assertEqual(result, "it''s me")

    def test_multiple_quotes(self):
        result = self.mod._escape_sql("she's 'fine'")
        self.assertEqual(result, "she''s ''fine''")

    def test_empty_string(self):
        self.assertEqual(self.mod._escape_sql(""), "")

    def test_returns_string(self):
        self.assertIsInstance(self.mod._escape_sql("x"), str)


if __name__ == "__main__":
    unittest.main()
