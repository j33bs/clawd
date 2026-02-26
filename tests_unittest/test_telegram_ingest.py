import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "telegram_ingest.py"
FIXTURE_PATH = REPO_ROOT / "workspace" / "fixtures" / "telegram_export_min.json"


def load_module():
    spec = importlib.util.spec_from_file_location("telegram_ingest", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TelegramIngestTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_parses_string_and_segment_array_text(self):
        rows = self.mod.parse_export_file(FIXTURE_PATH)
        texts = [row["text"] for row in rows]
        self.assertIn("Remember the 100 enhancements list?", texts)
        self.assertIn("Yes, it is in /workspace/docs/openclaw-100-enhancements.md", texts)
        # one whitespace-only service message should be dropped
        self.assertEqual(len(rows), 3)

    def test_ingest_writes_normalized_jsonl_and_dedupes(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "messages.jsonl"
            summary_first = self.mod.ingest_exports(FIXTURE_PATH, output)
            summary_second = self.mod.ingest_exports(FIXTURE_PATH, output)

            self.assertEqual(summary_first["inserted_rows"], 2)
            self.assertEqual(summary_first["total_rows"], 2)
            self.assertEqual(summary_second["inserted_rows"], 0)
            self.assertEqual(summary_second["total_rows"], 2)

            lines = output.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            parsed = [json.loads(line) for line in lines]
            row = parsed[0]
            self.assertEqual(row["source"], "telegram_export")
            self.assertIn("chat_id", row)
            self.assertIn("message_id", row)
            self.assertIn("timestamp", row)
            self.assertIn("hash", row)
            self.assertEqual(isinstance(row["text_len"], int), True)

    def test_hash_is_stable_for_same_content(self):
        rows = self.mod.parse_export_file(FIXTURE_PATH)
        duplicated = [row for row in rows if row["message_id"] == "2"]
        self.assertEqual(len(duplicated), 2)
        self.assertEqual(duplicated[0]["hash"], duplicated[1]["hash"])


if __name__ == "__main__":
    unittest.main()
