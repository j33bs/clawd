import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.scripts import telegram_memory_backfill  # noqa: E402


class TestTelegramMemoryBackfill(unittest.TestCase):
    def test_infer_role_prefers_self_name(self):
        row = {"sender_id": "1", "sender_name": "jeebs"}
        role = telegram_memory_backfill.infer_role(
            row,
            self_ids=set(),
            self_names={"jeebs"},
            assistant_names={"dali"},
        )
        self.assertEqual(role, "user")

    def test_backfill_rows_filters_allowlist_and_ingests(self):
        rows = [
            {
                "chat_id": "8159253715",
                "chat_title": "jeebs",
                "message_id": "1",
                "sender_id": "8159253715",
                "sender_name": "jeebs",
                "text": "Prefer concise operational summaries.",
                "timestamp": "2026-03-11T12:00:00Z",
                "source": "telegram_export",
                "meta": {},
            },
            {
                "chat_id": "999",
                "chat_title": "other",
                "message_id": "2",
                "sender_id": "2",
                "sender_name": "someone-else",
                "text": "Ignore this.",
                "timestamp": "2026-03-11T12:01:00Z",
                "source": "telegram_export",
                "meta": {},
            },
        ]
        ingest = mock.Mock(side_effect=[{"stored": True}, {"stored": False, "reason": "dedup"}])
        with mock.patch.object(telegram_memory_backfill, "ingest_telegram_exchange", ingest):
            summary = telegram_memory_backfill.backfill_rows(
                rows,
                allowed_chat_ids={"8159253715"},
                self_ids={"8159253715"},
                self_names={"jeebs"},
                assistant_names={"dali"},
                agent_scope="main",
            )
        self.assertEqual(summary["inserted_rows"], 1)
        self.assertEqual(summary["skipped_rows"], 1)
        ingest.assert_called_once()

    def test_load_rows_reads_normalized_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "messages.jsonl"
            row = {"chat_id": "8159253715", "text": "hello"}
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            loaded = telegram_memory_backfill.load_rows(path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["chat_id"], "8159253715")

    def test_load_rows_reads_openclaw_telegram_session(self):
        with tempfile.TemporaryDirectory() as td:
            sessions_dir = Path(td)
            index_path = sessions_dir / "sessions.json"
            session_id = "session-123"
            index_path.write_text(
                json.dumps(
                    {
                        "agent:main:main": {
                            "sessionId": session_id,
                            "displayName": "jeebs",
                            "lastTo": "telegram:8159253715",
                        }
                    }
                ),
                encoding="utf-8",
            )
            transcript_path = sessions_dir / f"{session_id}.jsonl"
            transcript_path.write_text(
                json.dumps({"type": "session", "id": session_id, "version": 3}) + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "id": "abc",
                        "timestamp": "2026-03-11T00:00:00Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Conversation info (untrusted metadata):\n```json\n"
                                        "{\"message_id\":\"1920\",\"sender_id\":\"8159253715\",\"timestamp\":\"2026-03-11T08:56:00Z\"}\n```\n\n"
                                        "Sender (untrusted metadata):\n```json\n"
                                        "{\"name\":\"jeebs\",\"username\":\"j33bs\",\"id\":\"8159253715\"}\n```\n\n"
                                        "wiring in some personality sourcing infrastructure"
                                    ),
                                }
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            loaded = telegram_memory_backfill.load_rows(transcript_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["chat_id"], "8159253715")
        self.assertIn("personality sourcing infrastructure", loaded[0]["text"])

    def test_load_rows_skips_reply_with_exactly_probes(self):
        with tempfile.TemporaryDirectory() as td:
            sessions_dir = Path(td)
            index_path = sessions_dir / "sessions.json"
            session_id = "session-456"
            index_path.write_text(
                json.dumps(
                    {
                        "agent:main:main": {
                            "sessionId": session_id,
                            "displayName": "jeebs",
                            "lastTo": "telegram:8159253715",
                        }
                    }
                ),
                encoding="utf-8",
            )
            transcript_path = sessions_dir / f"{session_id}.jsonl"
            transcript_path.write_text(
                json.dumps({"type": "session", "id": session_id, "version": 3}) + "\n"
                + json.dumps(
                    {
                        "type": "message",
                        "id": "probe",
                        "timestamp": "2026-03-11T00:00:00Z",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Reply with exactly: OK-54"}],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            loaded = telegram_memory_backfill.load_rows(transcript_path)
        self.assertEqual(loaded, [])


if __name__ == "__main__":
    unittest.main()
