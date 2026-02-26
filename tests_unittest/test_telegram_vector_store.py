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


if __name__ == "__main__":
    unittest.main()
