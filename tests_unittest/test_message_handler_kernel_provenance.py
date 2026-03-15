import asyncio
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "message_handler.py"


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


class _FakeRouter:
    def explain_route(self, intent, context_metadata=None, payload=None):
        return {
            "intent": intent,
            "surface": "telegram",
            "policy_profile": "surface:telegram",
            "reason": "telegram surface override",
            "chosen": {"provider": "openai_gpt54_chat", "model": "gpt-5.4"},
        }

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        return {
            "ok": True,
            "provider": "openai_gpt54_chat",
            "model": "gpt-5.4",
            "text": "Concrete Telegram reply.",
            "route_provenance": {
                "surface": "telegram",
                "policy_profile": "surface:telegram",
                "selected_provider": "openai_gpt54_chat",
                "selected_model": "gpt-5.4",
                "reason_code": "success",
            },
        }


class MessageHandlerKernelProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("message_handler_kernel_provenance_test", MODULE_PATH)

    def test_handler_attaches_kernel_metadata_to_runtime_context_and_reply_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            history_path = Path(td) / "telegram_history.json"
            provenance_path = Path(td) / "telegram_reply_provenance.jsonl"
            handler = self.mod.MessageHandler(
                "http://127.0.0.1:18789",
                "",
                router=_FakeRouter(),
                history_path=history_path,
            )

            captured = {}
            original_execute = handler.router.execute_with_escalation

            def _capture(intent, payload, context_metadata=None, validate_fn=None):
                captured.update(dict(context_metadata or {}))
                return original_execute(intent, payload, context_metadata, validate_fn)

            handler.router.execute_with_escalation = _capture

            async def _fake_send(**kwargs):
                return {"ok": True, "kwargs": kwargs}

            with (
                mock.patch.object(self.mod, "send_telegram_reply", side_effect=_fake_send),
                mock.patch.object(self.mod, "PROVENANCE_PATH", provenance_path),
            ):
                result = asyncio.run(
                    self.mod.handle_incoming_message(
                        {"message_id": "1", "chat_id": "chat-a", "content": "Need help with the repo"},
                        handler,
                    )
                )

            self.assertTrue(captured["kernel_id"].startswith("c_lawd:surface:telegram"))
            self.assertRegex(captured["kernel_hash"], r"^[0-9a-f]{64}$")
            self.assertEqual(captured["surface_overlay"], "surface:telegram|mode:conversation|memory:on")
            self.assertEqual(result["route_provenance"]["kernel_id"], captured["kernel_id"])
            self.assertEqual(result["route_provenance"]["kernel_hash"], captured["kernel_hash"])
            self.assertEqual(result["route_provenance"]["surface_overlay"], captured["surface_overlay"])
            rows = [
                json.loads(line)
                for line in provenance_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reply_id"], "1")
            self.assertEqual(rows[0]["policy_profile"], "surface:telegram")
            self.assertEqual(rows[0]["reason_code"], "success")
            self.assertEqual(rows[0]["provider"], "openai_gpt54_chat")
            self.assertEqual(rows[0]["model"], "gpt-5.4")
            self.assertEqual(rows[0]["memory_blocks"], [])
            self.assertEqual(rows[0]["files_touched"], [])
            self.assertEqual(rows[0]["tests_run"], [])
            self.assertEqual(rows[0]["uncertainties"], [])
            self.assertIn("route=openai_gpt54_chat/gpt-5.4", rows[0]["operator_visible_summary"])
            self.assertEqual(result["reply_provenance"]["reply_id"], "1")

    def test_handler_provenance_includes_recall_metadata_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            history_path = Path(td) / "telegram_history.json"
            provenance_path = Path(td) / "telegram_reply_provenance.jsonl"
            handler = self.mod.MessageHandler(
                "http://127.0.0.1:18789",
                "",
                router=_FakeRouter(),
                history_path=history_path,
            )

            async def _fake_send(**kwargs):
                return {"ok": True, "kwargs": kwargs}

            fake_recall = {
                "block": "TELEGRAM_MEMORY:\n- Jeebs wants Codex-direct Telegram replies.",
                "memory_blocks": [
                    {
                        "kind": "admitted_memory",
                        "chat_id": "chat-a",
                        "fact_text": "Jeebs wants Codex-direct Telegram replies.",
                        "source_message_ids": ["1"],
                        "evidence": [{"ref": "telegram:chat-a:1"}],
                    }
                ],
                "files_touched": ["/tmp/fake_memory.db"],
                "uncertainties": [],
            }

            with (
                mock.patch.object(self.mod, "send_telegram_reply", side_effect=_fake_send),
                mock.patch.object(self.mod, "PROVENANCE_PATH", provenance_path),
                mock.patch.object(self.mod, "build_recall_context", return_value=fake_recall),
            ):
                result = asyncio.run(
                    self.mod.handle_incoming_message(
                        {"message_id": "1", "chat_id": "chat-a", "content": "Need help with the repo"},
                        handler,
                    )
                )

            rows = [
                json.loads(line)
                for line in provenance_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(rows[0]["memory_blocks"], fake_recall["memory_blocks"])
            self.assertEqual(rows[0]["files_touched"], fake_recall["files_touched"])
            self.assertEqual(rows[0]["uncertainties"], [])
            self.assertEqual(result["reply_provenance"]["memory_blocks"], fake_recall["memory_blocks"])


if __name__ == "__main__":
    unittest.main()
