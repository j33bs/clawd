"""Tests for workspace/itc_pipeline/ingestion_boundary.py pure helpers.

Covers (no network, no Telegram):
- IngestedMessage.dedupe_key
- IngestedMessage.to_dict
- DedupeStore.is_duplicate / mark_processed (with tempfile)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from itc_pipeline.ingestion_boundary import DedupeStore, IngestedMessage  # noqa: E402


def _msg(**overrides) -> IngestedMessage:
    """Build a minimal IngestedMessage, optionally overriding fields."""
    defaults = {
        "source": "telegram",
        "chat_id": -1001234567890,
        "message_id": 42,
        "date": "2026-03-08T10:00:00Z",
        "sender_id": 999,
        "sender_name": "Test User",
        "chat_title": "Test Chat",
        "text": "Hello world",
        "raw_metadata": {},
    }
    defaults.update(overrides)
    return IngestedMessage(**defaults)


# ---------------------------------------------------------------------------
# IngestedMessage.dedupe_key
# ---------------------------------------------------------------------------

class TestDedupeKey(unittest.TestCase):
    """Tests for IngestedMessage.dedupe_key()."""

    def test_format(self):
        m = _msg(source="telegram", chat_id=-100, message_id=1)
        key = m.dedupe_key()
        self.assertEqual(key, "telegram:-100:1")

    def test_returns_string(self):
        self.assertIsInstance(_msg().dedupe_key(), str)

    def test_different_message_ids_differ(self):
        m1 = _msg(message_id=1)
        m2 = _msg(message_id=2)
        self.assertNotEqual(m1.dedupe_key(), m2.dedupe_key())

    def test_different_chat_ids_differ(self):
        m1 = _msg(chat_id=100)
        m2 = _msg(chat_id=200)
        self.assertNotEqual(m1.dedupe_key(), m2.dedupe_key())

    def test_same_fields_same_key(self):
        m1 = _msg(source="telegram", chat_id=-100, message_id=5)
        m2 = _msg(source="telegram", chat_id=-100, message_id=5)
        self.assertEqual(m1.dedupe_key(), m2.dedupe_key())


# ---------------------------------------------------------------------------
# IngestedMessage.to_dict
# ---------------------------------------------------------------------------

class TestToDict(unittest.TestCase):
    """Tests for IngestedMessage.to_dict()."""

    def test_returns_dict(self):
        self.assertIsInstance(_msg().to_dict(), dict)

    def test_source_present(self):
        d = _msg(source="telegram").to_dict()
        self.assertEqual(d["source"], "telegram")

    def test_chat_id_present(self):
        d = _msg(chat_id=-999).to_dict()
        self.assertEqual(d["chat_id"], -999)

    def test_text_present(self):
        d = _msg(text="hello").to_dict()
        self.assertEqual(d["text"], "hello")

    def test_json_serializable(self):
        d = _msg().to_dict()
        # Should not raise
        json.dumps(d)


# ---------------------------------------------------------------------------
# DedupeStore
# ---------------------------------------------------------------------------

class TestDedupeStore(unittest.TestCase):
    """Tests for DedupeStore.is_duplicate / mark_processed with tempfile."""

    def _store(self, td: str) -> DedupeStore:
        path = Path(td) / "dedupe_state.json"
        return DedupeStore(state_path=path)

    def test_new_key_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            self.assertFalse(store.is_duplicate("telegram:100:1"))

    def test_marked_key_is_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            store.mark_processed("telegram:100:2")
            self.assertTrue(store.is_duplicate("telegram:100:2"))

    def test_different_key_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            store.mark_processed("telegram:100:3")
            self.assertFalse(store.is_duplicate("telegram:100:99"))

    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "dedupe.json"
            store1 = DedupeStore(state_path=path)
            store1.mark_processed("telegram:100:5")
            store1.save()
            store2 = DedupeStore(state_path=path)
            self.assertTrue(store2.is_duplicate("telegram:100:5"))

    def test_multiple_marks(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            for i in range(5):
                store.mark_processed(f"telegram:100:{i}")
            for i in range(5):
                self.assertTrue(store.is_duplicate(f"telegram:100:{i}"))

    def test_is_duplicate_returns_bool(self):
        with tempfile.TemporaryDirectory() as td:
            store = self._store(td)
            self.assertIsInstance(store.is_duplicate("key"), bool)


if __name__ == "__main__":
    unittest.main()
