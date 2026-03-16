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

    def test_build_telegram_memory_context_prioritizes_thread_and_assistant_turns(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "knowledge_base" / "data"
            jsonl_path = data_dir / "telegram_messages.jsonl"
            rows = [
                {
                    "chat_id": "8159253715",
                    "chat_title": "jeebs",
                    "message_id": "100",
                    "author_name": "jeebs",
                    "role": "user",
                    "created_at": "2026-03-15T01:00:00Z",
                    "content": "Can you rewire Telegram routing?",
                    "meta": {},
                },
                {
                    "chat_id": "8159253715",
                    "chat_title": "jeebs",
                    "message_id": "101",
                    "author_name": "Dali",
                    "role": "assistant",
                    "created_at": "2026-03-15T01:01:00Z",
                    "content": "I'll move Telegram onto the shared router path.",
                    "meta": {
                        "reply_to_message_id": "100",
                        "exec_tags": ["decision", "binding"],
                        "trust_epoch": "epoch-7",
                    },
                },
                {
                    "chat_id": "8159253715",
                    "chat_title": "jeebs",
                    "message_id": "102",
                    "author_name": "jeebs",
                    "role": "user",
                    "created_at": "2026-03-15T01:02:00Z",
                    "content": "What about the context packet?",
                    "meta": {},
                },
                {
                    "chat_id": "999",
                    "chat_title": "other-chat",
                    "message_id": "103",
                    "author_name": "jeebs",
                    "role": "user",
                    "created_at": "2026-03-15T01:03:00Z",
                    "content": "This should not bleed across chats.",
                    "meta": {},
                },
            ]
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            jsonl_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            with mock.patch.object(telegram_memory, "TELEGRAM_MEMORY_PATH", jsonl_path):
                context = telegram_memory.build_telegram_memory_context(
                    chat_id="8159253715",
                    author_name="jeebs",
                    exclude_message_id="102",
                    thread_message_id="100",
                    limit=2,
                )

            self.assertEqual(len(context), 2)
            self.assertIn("assistant", context[-1])
            self.assertIn("commitment", context[-1])
            self.assertIn("reply-to 100", context[-1])
            self.assertIn("decision", context[-1])
            self.assertIn("trust epoch-7", context[-1])
            self.assertNotIn("bleed across chats", "\n".join(context))

    def test_sanitize_telegram_memory_archive_filters_transcript_noise(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "knowledge_base" / "data"
            jsonl_path = data_dir / "telegram_messages.jsonl"
            state_path = data_dir / "telegram_memory_ingest_state.json"
            rows = [
                {
                    "chat_id": "8159253715",
                    "chat_title": "jeebs",
                    "message_id": "200",
                    "author_name": "jeebs",
                    "role": "user",
                    "created_at": "2026-03-16T10:00:00Z",
                    "content": "Prefer concise operational responses.",
                    "source": "telegram",
                    "meta": {},
                },
                {
                    "chat_id": "8159253715",
                    "chat_title": "jeebs",
                    "message_id": "201",
                    "author_name": "jeebs",
                    "role": "user",
                    "created_at": "2026-03-16T10:01:00Z",
                    "content": "System: Exec denied (gateway id=abc, approval-timeout)",
                    "source": "openclaw_telegram_session",
                    "meta": {},
                },
                {
                    "chat_id": "8159253715",
                    "chat_title": "jeebs",
                    "message_id": "202",
                    "author_name": "Dali",
                    "role": "assistant",
                    "created_at": "2026-03-16T10:02:00Z",
                    "content": "I fixed Telegram routing and switched replies back to MiniMax.",
                    "source": "telegram_gateway_reply",
                    "meta": {"reply_to_message_id": "200"},
                },
            ]
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            jsonl_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            with mock.patch.object(telegram_memory, "TELEGRAM_MEMORY_PATH", jsonl_path):
                with mock.patch.object(telegram_memory, "TELEGRAM_MEMORY_STATE_PATH", state_path):
                    summary = telegram_memory.sanitize_telegram_memory_archive()

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["rows_before"], 3)
            self.assertEqual(summary["rows_after"], 2)
            stored = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual([row["message_id"] for row in stored], ["200", "202"])


if __name__ == "__main__":
    unittest.main()
