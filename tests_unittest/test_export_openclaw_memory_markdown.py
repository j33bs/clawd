import json
import tempfile
import unittest
from pathlib import Path
import importlib.util as ilu
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "export_openclaw_memory_markdown.py"
_spec = ilu.spec_from_file_location("export_openclaw_memory_markdown_real", str(MODULE_PATH))
mod = ilu.module_from_spec(_spec)
sys.modules["export_openclaw_memory_markdown_real"] = mod
_spec.loader.exec_module(mod)


class TestExportOpenClawMemoryMarkdown(unittest.TestCase):
    def test_exports_recent_external_conversations_to_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            telegram_dir = root / "workspace" / "state_runtime" / "ingest" / "telegram_normalized"
            telegram_dir.mkdir(parents=True)
            telegram_path = telegram_dir / "messages.jsonl"
            session_dir = root / ".openclaw" / "agents" / "research" / "sessions"
            session_dir.mkdir(parents=True)
            telegram_path.write_text(
                json.dumps(
                    {
                        "chat_id": "chat-1",
                        "chat_title": "Jeebs Chat",
                        "timestamp": "2026-03-10T13:00:00Z",
                        "sender_name": "jeebs",
                        "text": "Remember that Discord and Telegram should both feed recall.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (session_dir / "session-1.jsonl").write_text(
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-10T14:00:00Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Conversation info (untrusted metadata):\n```json\n{\"group_channel\":\"#clawd-chat-gpt\"}\n```\n\nSender (untrusted metadata):\n```json\n{\"name\":\"jeeebs\"}\n```\n\nremember the Discord side too",
                                }
                            ],
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-10T15:00:00Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Continue where you left off. The previous model attempt failed or timed out.",
                                }
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "USER.md").write_text("# USER\n\n- Prefers direct answers.\n", encoding="utf-8")

            output_path = root / "memory" / "ingest" / "external_conversations.md"
            summary = mod.export_openclaw_memory_markdown(
                root,
                output_path=output_path,
                conversation_limit=10,
                session_limit=10,
                dali_inbox_path=root / "missing_inbox.jsonl",
                dali_outbox_path=root / "missing_outbox.jsonl",
                telegram_path=telegram_path,
                session_dirs=[session_dir],
            )

            self.assertEqual(summary["status"], "ok")
            self.assertTrue(output_path.is_file())
            text = output_path.read_text(encoding="utf-8")
            self.assertIn("# External Conversation Memory", text)
            self.assertIn("telegram_normalized", text)
            self.assertIn("Discord and Telegram should both feed recall", text)
            self.assertIn("Cross-Agent Session Messages", text)
            self.assertIn("remember the Discord side too", text)
            self.assertNotIn("Continue where you left off", text)

    def test_writes_empty_state_when_no_external_conversations_exist(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output_path = root / "memory" / "ingest" / "external_conversations.md"

            summary = mod.export_openclaw_memory_markdown(
                root,
                output_path=output_path,
                conversation_limit=10,
                session_limit=10,
                dali_inbox_path=root / "missing_inbox.jsonl",
                dali_outbox_path=root / "missing_outbox.jsonl",
                telegram_path=root / "missing_telegram.jsonl",
                session_dirs=[root / "missing_sessions"],
            )

            self.assertEqual(summary["conversation_entries"], 0)
            self.assertEqual(summary["session_entries"], 0)
            self.assertIn("No external conversation history is available yet.", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
