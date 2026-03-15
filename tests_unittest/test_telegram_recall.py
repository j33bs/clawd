import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "telegram_vector_store.py"
RECALL_MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "telegram_recall.py"
MEMORY_DB_MODULE_PATH = REPO_ROOT / "workspace" / "profile" / "user_memory_db.py"


def load_module(name: str, path: Path):
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TelegramRecallTests(unittest.TestCase):
    def setUp(self):
        self.store_mod = load_module("telegram_vector_store", STORE_MODULE_PATH)
        self.recall_mod = load_module("telegram_recall", RECALL_MODULE_PATH)
        self.memory_mod = load_module("user_memory_db", MEMORY_DB_MODULE_PATH)

    def _seed_store(self, store_dir: Path, normalized_path: Path) -> None:
        rows = [
            {
                "hash": "recall-a",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "1",
                "timestamp": "2026-02-20T10:00:00Z",
                "sender_name": "jeebs",
                "text": "Remember we discussed telegram vector memory enhancements and recall behavior.",
                "reply_to_message_id": None,
            },
            {
                "hash": "recall-b",
                "chat_id": "111",
                "chat_title": "c_lawd chat",
                "message_id": "2",
                "timestamp": "2026-02-20T10:01:00Z",
                "sender_name": "c_lawd",
                "text": "Yes, semantic search should load historical context at session start.",
                "reply_to_message_id": "1",
            },
            {
                "hash": "recall-c",
                "chat_id": "222",
                "chat_title": "other chat",
                "message_id": "3",
                "timestamp": "2026-02-20T10:02:00Z",
                "sender_name": "someone-else",
                "text": "Remember a completely different thread about dinner plans.",
                "reply_to_message_id": None,
            },
        ]
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        with normalized_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=True) + "\n")

        self.store_mod.build_store(
            normalized_path=normalized_path,
            store_dir=store_dir,
            embedder_name="keyword_stub",
            force_backend="jsonl",
        )

    def test_recall_toggle_and_injection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_dir = root / "store"
            normalized = root / "normalized.jsonl"
            self._seed_store(store_dir, normalized)

            disabled = self.recall_mod.inject_telegram_recall_context(
                "remember what we discussed",
                env={"OPENCLAW_TELEGRAM_RECALL": "0"},
                store_dir=store_dir,
            )
            self.assertEqual(disabled, "remember what we discussed")

            enabled = self.recall_mod.inject_telegram_recall_context(
                "remember what we discussed",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_RECALL_TOPK": "2",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "500",
                },
                store_dir=store_dir,
            )
            self.assertIn("TELEGRAM_RECALL:", enabled)
            self.assertIn("remember what we discussed", enabled)

    def test_recall_caps_respected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_dir = root / "store"
            normalized = root / "normalized.jsonl"
            self._seed_store(store_dir, normalized)

            block = self.recall_mod.build_recall_block(
                "remember vector memory behavior",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_RECALL_TOPK": "6",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "120",
                },
                store_dir=store_dir,
            )
            self.assertLessEqual(len(block), 120)

    def test_recall_can_scope_to_explicit_chat_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_dir = root / "store"
            normalized = root / "normalized.jsonl"
            self._seed_store(store_dir, normalized)

            block = self.recall_mod.build_recall_block(
                "remember what we discussed",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_RECALL_TOPK": "4",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "500",
                },
                chat_id="111",
                store_dir=store_dir,
            )
            self.assertIn("semantic search should load historical context", block)
            self.assertNotIn("dinner plans", block)

    def test_recall_prefers_admitted_governed_memory_for_chat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_dir = root / "store"
            normalized = root / "normalized.jsonl"
            self._seed_store(store_dir, normalized)

            db_path = root / "workspace" / "profile" / "user_memory.db"
            candidate = self.memory_mod.propose_telegram_memory_fact(
                chat_id="111",
                fact_text="Jeebs wants Telegram replies to feel like Codex-direct.",
                evidence=[{"ref": "telegram:111:1", "quote": "Codex-direct"}],
            )
            record = self.memory_mod.admit_telegram_memory_fact(db_path, candidate)
            self.assertEqual(record["status"], "admitted")

            block = self.recall_mod.build_recall_block(
                "remember Codex-direct Telegram preferences",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_RECALL_TOPK": "4",
                    "OPENCLAW_TELEGRAM_MEMORY_TOPK": "2",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "500",
                    "OPENCLAW_USER_MEMORY_DB_PATH": str(db_path),
                },
                chat_id="111",
                store_dir=store_dir,
            )
            self.assertIn("TELEGRAM_MEMORY:", block)
            self.assertIn("Codex-direct", block)
            self.assertNotIn("TELEGRAM_RECALL:", block)

    def test_recall_context_reports_memory_blocks_and_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_dir = root / "store"
            normalized = root / "normalized.jsonl"
            self._seed_store(store_dir, normalized)

            ctx = self.recall_mod.build_recall_context(
                "remember what we discussed",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_RECALL_TOPK": "2",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "500",
                    "OPENCLAW_USER_MEMORY_DB_PATH": str(root / "workspace" / "profile" / "user_memory.db"),
                },
                chat_id="111",
                store_dir=store_dir,
            )
            self.assertTrue(ctx["block"].startswith("TELEGRAM_RECALL:"))
            self.assertGreaterEqual(len(ctx["memory_blocks"]), 1)
            self.assertEqual(ctx["memory_blocks"][0]["kind"], "semantic_recall")
            self.assertIn(str(store_dir), ctx["files_touched"])

    def test_recall_stays_chat_scoped_unless_global_scope_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store_dir = root / "store"
            normalized = root / "normalized.jsonl"
            self._seed_store(store_dir, normalized)

            db_path = root / "workspace" / "profile" / "user_memory.db"
            global_candidate = self.memory_mod.propose_telegram_memory_fact(
                chat_id="111",
                fact_text="Shared global Telegram preference.",
                evidence=[{"ref": "telegram:111:1", "quote": "Shared global Telegram preference."}],
                privacy_scope="global",
                operator_approved=True,
            )
            global_record = self.memory_mod.admit_telegram_memory_fact(db_path, global_candidate)
            self.assertEqual(global_record["status"], "admitted")

            default_scope = self.recall_mod.build_recall_block(
                "remember shared global Telegram preference",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_MEMORY_TOPK": "2",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "500",
                    "OPENCLAW_USER_MEMORY_DB_PATH": str(db_path),
                },
                chat_id="222",
                store_dir=store_dir,
            )
            self.assertNotIn("TELEGRAM_MEMORY:", default_scope)

            explicit_scope = self.recall_mod.build_recall_block(
                "remember shared global Telegram preference",
                env={
                    "OPENCLAW_TELEGRAM_RECALL": "1",
                    "OPENCLAW_TELEGRAM_MEMORY_TOPK": "2",
                    "OPENCLAW_TELEGRAM_MEMORY_SCOPE": "chat+global",
                    "OPENCLAW_TELEGRAM_RECALL_MAX_CHARS": "500",
                    "OPENCLAW_USER_MEMORY_DB_PATH": str(db_path),
                },
                chat_id="222",
                store_dir=store_dir,
            )
            self.assertIn("TELEGRAM_MEMORY:", explicit_scope)
            self.assertIn("Shared global Telegram preference.", explicit_scope)


if __name__ == "__main__":
    unittest.main()
