import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import telegram_memory  # noqa: E402


class TestTelegramMemory(unittest.TestCase):
    def test_ingest_telegram_exchange_writes_and_dedupes(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "knowledge_base" / "data"
            jsonl_path = data_dir / "telegram_messages.jsonl"
            state_path = data_dir / "telegram_memory_ingest_state.json"

            hive_store = mock.Mock()
            hive_store.put.return_value = {"stored": True, "content_hash": "abc"}
            graph_store = mock.Mock()
            graph_store.add_entity.return_value = "graph123"

            with mock.patch.object(telegram_memory, "TELEGRAM_MEMORY_PATH", jsonl_path):
                with mock.patch.object(telegram_memory, "TELEGRAM_MEMORY_STATE_PATH", state_path):
                    with mock.patch.object(telegram_memory, "KB_DATA_DIR", data_dir):
                        with mock.patch.object(telegram_memory, "HiveMindStore", return_value=hive_store):
                            with mock.patch.object(telegram_memory, "KnowledgeGraphStore", return_value=graph_store):
                                first = telegram_memory.ingest_telegram_exchange(
                                    chat_id="8159253715",
                                    chat_title="jeebs",
                                    message_id="1001",
                                    author_id="8159253715",
                                    author_name="jeebs",
                                    role="user",
                                    content="Keep notifications low-noise.",
                                    created_at="2026-03-11T12:00:00Z",
                                    agent_scope="main",
                                )
                                second = telegram_memory.ingest_telegram_exchange(
                                    chat_id="8159253715",
                                    chat_title="jeebs",
                                    message_id="1001",
                                    author_id="8159253715",
                                    author_name="jeebs",
                                    role="user",
                                    content="Keep notifications low-noise.",
                                    created_at="2026-03-11T12:00:00Z",
                                    agent_scope="main",
                                )

            self.assertTrue(first["stored"])
            self.assertEqual(second["reason"], "dedup")
            rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["chat_title"], "jeebs")


if __name__ == "__main__":
    unittest.main()
