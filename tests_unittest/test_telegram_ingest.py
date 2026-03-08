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


class TestParseTimestamp(unittest.TestCase):
    """Tests for telegram_ingest.parse_timestamp() — ISO normalizer."""

    def setUp(self):
        self.mod = load_module()

    def test_none_returns_epoch(self):
        self.assertEqual(self.mod.parse_timestamp(None), "1970-01-01T00:00:00Z")

    def test_empty_string_returns_epoch(self):
        self.assertEqual(self.mod.parse_timestamp(""), "1970-01-01T00:00:00Z")

    def test_invalid_string_returns_epoch(self):
        self.assertEqual(self.mod.parse_timestamp("not-a-date"), "1970-01-01T00:00:00Z")

    def test_valid_iso_z_passthrough(self):
        result = self.mod.parse_timestamp("2026-03-08T12:00:00Z")
        self.assertEqual(result, "2026-03-08T12:00:00Z")

    def test_valid_iso_offset_normalized_to_z(self):
        result = self.mod.parse_timestamp("2026-03-08T12:00:00+00:00")
        self.assertEqual(result, "2026-03-08T12:00:00Z")

    def test_returns_string(self):
        self.assertIsInstance(self.mod.parse_timestamp("2026-01-01"), str)

    def test_microseconds_stripped(self):
        result = self.mod.parse_timestamp("2026-03-08T12:00:00.123456Z")
        self.assertEqual(result, "2026-03-08T12:00:00Z")

    def test_integer_returns_epoch(self):
        # Non-string/None types coerced via str(); "123" is not a valid ISO → epoch
        result = self.mod.parse_timestamp(99999)
        self.assertEqual(result, "1970-01-01T00:00:00Z")


class TestFlattenText(unittest.TestCase):
    """Tests for telegram_ingest.flatten_text() — text extraction from mixed types."""

    def setUp(self):
        self.mod = load_module()

    def test_string_returned_unchanged(self):
        self.assertEqual(self.mod.flatten_text("hello world"), "hello world")

    def test_empty_string_returned(self):
        self.assertEqual(self.mod.flatten_text(""), "")

    def test_list_of_strings_joined(self):
        result = self.mod.flatten_text(["hello", " ", "world"])
        self.assertEqual(result, "hello world")

    def test_list_of_dicts_with_text_key(self):
        result = self.mod.flatten_text([{"text": "hello"}, {"text": " world"}])
        self.assertEqual(result, "hello world")

    def test_mixed_list(self):
        result = self.mod.flatten_text(["prefix", {"text": "-suffix"}])
        self.assertEqual(result, "prefix-suffix")

    def test_non_string_non_list_returns_empty(self):
        self.assertEqual(self.mod.flatten_text(42), "")
        self.assertEqual(self.mod.flatten_text(None), "")
        self.assertEqual(self.mod.flatten_text({}), "")

    def test_list_item_without_text_key_skipped(self):
        result = self.mod.flatten_text([{"other": "ignored"}, "kept"])
        self.assertEqual(result, "kept")

    def test_returns_string(self):
        self.assertIsInstance(self.mod.flatten_text("x"), str)


class TestStableHash(unittest.TestCase):
    """Tests for telegram_ingest.stable_hash() — deterministic SHA256."""

    def setUp(self):
        self.mod = load_module()

    def test_returns_string(self):
        self.assertIsInstance(self.mod.stable_hash(["a", "b"]), str)

    def test_64_char_hex(self):
        result = self.mod.stable_hash(["a", "b"])
        self.assertEqual(len(result), 64)
        int(result, 16)  # hex-decodable

    def test_deterministic(self):
        h1 = self.mod.stable_hash(["chat", "42", "2026"])
        h2 = self.mod.stable_hash(["chat", "42", "2026"])
        self.assertEqual(h1, h2)

    def test_different_parts_different_hash(self):
        h1 = self.mod.stable_hash(["a"])
        h2 = self.mod.stable_hash(["b"])
        self.assertNotEqual(h1, h2)

    def test_empty_list_produces_hash(self):
        result = self.mod.stable_hash([])
        self.assertEqual(len(result), 64)

    def test_order_sensitive(self):
        h1 = self.mod.stable_hash(["a", "b"])
        h2 = self.mod.stable_hash(["b", "a"])
        self.assertNotEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
