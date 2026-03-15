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

from api import discord_memory  # noqa: E402


class TestDiscordMemory(unittest.TestCase):
    def test_ingest_discord_exchange_writes_jsonl_and_storage(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "knowledge_base" / "data"
            jsonl_path = data_dir / "discord_messages.jsonl"
            research_path = data_dir / "discord_research_messages.jsonl"

            hive_store = mock.Mock()
            hive_store.put.return_value = {"stored": True, "content_hash": "abc"}
            graph_store = mock.Mock()
            graph_store.add_entity.return_value = "graph123"

            with mock.patch.object(discord_memory, "DISCORD_MEMORY_PATH", jsonl_path):
                with mock.patch.object(discord_memory, "DISCORD_RESEARCH_PATH", research_path):
                    with mock.patch.object(discord_memory, "KB_DATA_DIR", data_dir):
                        with mock.patch.object(discord_memory, "HiveMindStore", return_value=hive_store):
                            with mock.patch.object(discord_memory, "KnowledgeGraphStore", return_value=graph_store):
                                result = discord_memory.ingest_discord_exchange(
                                    guild_id=1,
                                    guild_name="oc",
                                    channel_id=148,
                                    channel_name="gpt54-chat",
                                    message_id="999",
                                    author_id=42,
                                    author_name="jeebs",
                                    role="user",
                                    content="Prefer concise sim summaries.",
                                    attachments=["https://example.com/chart.png"],
                                    created_at="2026-03-11T12:00:00Z",
                                    agent_scope="main",
                                    ingest_research=True,
                                )

            self.assertTrue(result["stored"])
            stored_rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(stored_rows[0]["channel_name"], "gpt54-chat")
            self.assertEqual(stored_rows[0]["message_id"], "999")
            research_rows = [json.loads(line) for line in research_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(research_rows[0]["message_id"], "999")
            hive_store.put.assert_called_once()
            self.assertEqual(graph_store.add_entity.call_count, 2)

    def test_build_discord_memory_context_filters_to_user_and_channel(self):
        with tempfile.TemporaryDirectory() as td:
            jsonl_path = Path(td) / "discord_messages.jsonl"
            rows = [
                {
                    "message_id": "1",
                    "channel_id": 148,
                    "channel_name": "gpt54-chat",
                    "author_name": "jeebs",
                    "role": "user",
                    "content": "I care about low-noise ops reporting.",
                    "created_at": "2026-03-09T12:00:00Z",
                },
                {
                    "message_id": "2",
                    "channel_id": 999,
                    "channel_name": "random",
                    "author_name": "someone-else",
                    "role": "user",
                    "content": "Ignore this.",
                    "created_at": "2026-03-10T12:00:00Z",
                },
                {
                    "message_id": "3",
                    "channel_id": 148,
                    "channel_name": "gpt54-chat",
                    "author_name": "Dali",
                    "role": "assistant",
                    "content": "Assistant reply.",
                    "created_at": "2026-03-11T12:00:00Z",
                },
            ]
            jsonl_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with mock.patch.object(discord_memory, "DISCORD_MEMORY_PATH", jsonl_path):
                context = discord_memory.build_discord_memory_context(
                    channel_id=148,
                    author_name="jeebs",
                    exclude_message_id="4",
                    limit=3,
                )
            self.assertEqual(len(context), 1)
            self.assertIn("low-noise ops reporting", context[0])


if __name__ == "__main__":
    unittest.main()
