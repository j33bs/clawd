import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core_infra.econ_log import append_jsonl, flush_pending


class TestEconLog(unittest.TestCase):
    def test_appends_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "observe.jsonl")
            append_jsonl(path, {"a": 1, "b": "x"})
            append_jsonl(path, {"a": 2, "b": "y"})

            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]

            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["a"], 1)
            self.assertEqual(lines[1]["b"], "y")

    def test_utf8_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "utf8.jsonl")
            append_jsonl(path, {"text": "snowman ☃"})
            with open(path, "r", encoding="utf-8") as f:
                row = json.loads(f.readline())
            self.assertEqual(row["text"], "snowman ☃")

    def test_batches_fsync_calls(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "batch.jsonl")
            with patch("core_infra.econ_log.os.fsync") as fsync_mock:
                for i in range(120):
                    append_jsonl(path, {"i": i})
                flush_pending(path)
            # 120 writes with batch size 50 -> at most 3 fsyncs.
            self.assertLessEqual(fsync_mock.call_count, 3)
            with open(path, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(rows), 120)


if __name__ == "__main__":
    unittest.main()
