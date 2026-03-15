import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import importlib.util as ilu
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "profile" / "user_memory_db.py"
_spec = ilu.spec_from_file_location("user_memory_db_real", str(MODULE_PATH))
mod = ilu.module_from_spec(_spec)
sys.modules["user_memory_db_real"] = mod
_spec.loader.exec_module(mod)


class TestUserMemoryDb(unittest.TestCase):
    def test_sync_builds_db_and_export_from_memory_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memory").mkdir(parents=True)
            (root / "nodes" / "dali").mkdir(parents=True)
            (root / "nodes" / "c_lawd").mkdir(parents=True)

            (root / "USER.md").write_text(
                "# USER.md\n\n"
                "- **What to call them:** jeebs\n"
                "## Preferences\n"
                "- Research: Use Grokipedia over Wikipedia\n",
                encoding="utf-8",
            )
            (root / "MEMORY.md").write_text(
                "# MEMORY.md\n\n"
                "## User Preferences\n"
                "- Daily Close: Ask whether TACTI tactics were used that day\n"
                "## Current Projects\n"
                "- Memory unification sprint active\n",
                encoding="utf-8",
            )
            (root / "memory" / "2026-03-10.md").write_text(
                "# March 10th, 2026\n\n"
                "## Mesh Heartbeat to Dali\n"
                "- Sent message about memory database sync\n",
                encoding="utf-8",
            )
            (root / "nodes" / "dali" / "MEMORY.md").write_text(
                "# Dali Memory\n\n"
                "## Notes\n"
                "- Jeebs prefers concise summaries.\n",
                encoding="utf-8",
            )
            (root / "nodes" / "c_lawd" / "MEMORY.md").write_text(
                "# c_lawd Memory\n\n"
                "## Notes\n"
                "- Jeebs is building OpenClaw.\n",
                encoding="utf-8",
            )

            db_path = root / "workspace" / "profile" / "user_memory.db"
            export_path = root / "workspace" / "profile" / "user_memory.jsonl"
            summary = mod.sync_user_memory(root, db_path, export_path)

            self.assertEqual(summary["status"], "ok")
            self.assertTrue(db_path.is_file())
            self.assertTrue(export_path.is_file())
            self.assertGreaterEqual(summary["entry_count"], 5)
            self.assertIn("preference", summary["by_category"])
            self.assertIn("dali", summary["by_contributor"])

            conn = sqlite3.connect(str(db_path))
            try:
                rows = conn.execute(
                    "SELECT contributor, category, title, text FROM user_memory_entries ORDER BY contributor, title"
                ).fetchall()
            finally:
                conn.close()
            self.assertTrue(any(row[0] == "dali" for row in rows))
            self.assertTrue(any(row[1] == "project" for row in rows))

            exported = [json.loads(line) for line in export_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(any(item["source"] == "user_profile" for item in exported))

    def test_sync_ingests_dali_messenger_and_telegram_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "workspace" / "state_runtime" / "ingest" / "telegram_normalized").mkdir(parents=True)
            inbox = root / "runtime_inbox.jsonl"
            telegram = root / "workspace" / "state_runtime" / "ingest" / "telegram_normalized" / "messages.jsonl"

            inbox.write_text(
                json.dumps(
                    {
                        "from": "dali",
                        "text": "Quick update from Dali about the memory graph.",
                        "sent_at": "2026-03-10T12:00:00",
                        "received_at": "2026-03-10T12:00:01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            telegram.write_text(
                json.dumps(
                    {
                        "chat_id": "chat-1",
                        "chat_title": "Jeebs Chat",
                        "timestamp": "2026-03-10T13:00:00Z",
                        "sender_name": "jeebs",
                        "text": "Remember the project preferences and prior conversations.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            db_path = root / "workspace" / "profile" / "user_memory.db"
            export_path = root / "workspace" / "profile" / "user_memory.jsonl"
            summary = mod.sync_user_memory(
                root,
                db_path,
                export_path,
                dali_inbox_path=inbox,
                dali_outbox_path=root / "missing_outbox.jsonl",
                telegram_path=telegram,
            )

            self.assertGreaterEqual(summary["entry_count"], 2)
            rows = mod.query_user_memory(db_path, category="conversation", limit=10)
            self.assertTrue(any(row["source_kind"] == "dali_messenger" for row in rows))
            self.assertTrue(any(row["source_kind"] == "telegram_normalized" for row in rows))

    def test_query_filters_by_text_and_contributor(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "workspace" / "profile" / "user_memory.db"
            export_path = root / "workspace" / "profile" / "user_memory.jsonl"
            summary = mod.sync_user_memory(
                root,
                db_path,
                export_path,
                dali_inbox_path=root / "missing_inbox.jsonl",
                dali_outbox_path=root / "missing_outbox.jsonl",
                telegram_path=root / "missing_telegram.jsonl",
            )
            self.assertEqual(summary["entry_count"], 0)

            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO user_memory_entries (
                        id, ts, contributor, source_path, source_kind, category,
                        section_path, title, text, refs_json, line_no
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "abc",
                        "2026-03-10T00:00:00Z",
                        "dali",
                        "nodes/dali/MEMORY.md",
                        "node_memory",
                        "preference",
                        "Notes",
                        "Summaries",
                        "Jeebs prefers concise summaries.",
                        json.dumps(["contributor:dali", "category:preference"]),
                        1,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            rows = mod.query_user_memory(db_path, q="concise", contributor="dali", limit=5)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["category"], "preference")

    def test_telegram_memory_fact_requires_evidence_and_stays_chat_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "workspace" / "profile" / "user_memory.db"

            candidate = mod.propose_telegram_memory_fact(
                chat_id="chat-1",
                fact_text="Jeebs prefers evidence-backed replies.",
                evidence=[],
            )
            record = mod.admit_telegram_memory_fact(db_path, candidate)
            self.assertEqual(record["status"], "rejected")
            self.assertEqual(record["contradiction_state"], "insufficient_evidence")

            approved = mod.propose_telegram_memory_fact(
                chat_id="chat-1",
                fact_text="Jeebs prefers evidence-backed replies.",
                evidence=[{"ref": "telegram:chat-1:42", "quote": "evidence-backed replies"}],
            )
            admitted = mod.admit_telegram_memory_fact(db_path, approved)
            self.assertEqual(admitted["status"], "admitted")
            rows = mod.query_telegram_memory(db_path, chat_id="chat-1", q="evidence-backed", limit=5)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fact_text"], "Jeebs prefers evidence-backed replies.")
            self.assertEqual(mod.query_telegram_memory(db_path, chat_id="chat-2", q="evidence-backed", limit=5), [])

    def test_telegram_memory_fact_flags_contradictions_and_global_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "workspace" / "profile" / "user_memory.db"

            first = mod.propose_telegram_memory_fact(
                chat_id="chat-1",
                fact_text="Jeebs prefers concise replies.",
                evidence=[{"ref": "telegram:chat-1:1"}],
            )
            admitted = mod.admit_telegram_memory_fact(db_path, first)
            self.assertEqual(admitted["status"], "admitted")

            conflicting = mod.propose_telegram_memory_fact(
                chat_id="chat-1",
                fact_text="Jeebs prefers very long replies.",
                evidence=[{"ref": "telegram:chat-1:2"}],
            )
            reviewed = mod.admit_telegram_memory_fact(db_path, conflicting)
            self.assertEqual(reviewed["status"], "needs_review")
            self.assertEqual(reviewed["contradiction_state"], "conflicted")

            global_candidate = mod.propose_telegram_memory_fact(
                chat_id="chat-1",
                fact_text="Share this preference across all chats.",
                evidence=[{"ref": "telegram:chat-1:3"}],
                privacy_scope="global",
            )
            global_result = mod.admit_telegram_memory_fact(db_path, global_candidate)
            self.assertEqual(global_result["status"], "needs_review")
            self.assertEqual(global_result["agency_state"], "operator_review")

    def test_query_telegram_memory_requires_explicit_scope_for_global_facts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "workspace" / "profile" / "user_memory.db"

            global_candidate = mod.propose_telegram_memory_fact(
                chat_id="chat-1",
                fact_text="Shared preference approved for all chats.",
                evidence=[{"ref": "telegram:chat-1:3"}],
                privacy_scope="global",
                operator_approved=True,
            )
            global_result = mod.admit_telegram_memory_fact(db_path, global_candidate)
            self.assertEqual(global_result["status"], "admitted")
            self.assertEqual(global_result["privacy_scope"], "global")

            self.assertEqual(
                mod.query_telegram_memory(db_path, chat_id="chat-2", q="shared preference", limit=5),
                [],
            )

            rows = mod.query_telegram_memory(
                db_path,
                chat_id="chat-2",
                q="shared preference",
                limit=5,
                scope="chat+global",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fact_text"], "Shared preference approved for all chats.")


if __name__ == "__main__":
    unittest.main()
