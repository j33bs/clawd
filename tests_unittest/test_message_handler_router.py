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
    def __init__(self):
        self.executions = []

    def explain_route(self, intent, context_metadata=None, payload=None):
        return {
            "intent": intent,
            "surface": "telegram",
            "policy_profile": "surface:telegram",
            "reason": "telegram surface override",
            "chosen": {"provider": "openai_gpt54_chat", "model": "gpt-5.4"},
        }

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        self.executions.append(
            {
                "intent": intent,
                "payload": payload,
                "context_metadata": dict(context_metadata or {}),
            }
        )
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


class MessageHandlerRouterTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("message_handler_router_test", MODULE_PATH)

    def test_handler_uses_router_and_persists_history_per_chat(self):
        with tempfile.TemporaryDirectory() as td:
            history_path = Path(td) / "telegram_history.json"
            fake_router = _FakeRouter()
            handler = self.mod.MessageHandler(
                "http://127.0.0.1:18789",
                "",
                router=fake_router,
                history_path=history_path,
            )

            async def _fake_send(**kwargs):
                return {"ok": True, "kwargs": kwargs}

            with mock.patch.object(self.mod, "send_telegram_reply", side_effect=_fake_send):
                first_result = asyncio.run(
                    self.mod.handle_incoming_message(
                        {"message_id": "1", "chat_id": "chat-a", "content": "Need help with the repo"},
                        handler,
                    )
                )
                second_result = asyncio.run(
                    self.mod.handle_incoming_message(
                        {"message_id": "2", "chat_id": "chat-b", "content": "Different chat"},
                        handler,
                    )
                )

            self.assertEqual(len(fake_router.executions), 2)
            first = fake_router.executions[0]
            prompt = first["payload"]["messages"][0]["content"]
            self.assertIn("c_lawd Conversation Kernel", prompt)
            self.assertEqual(first["context_metadata"]["surface"], "telegram")
            self.assertEqual(first["context_metadata"]["chat_id"], "chat-a")
            self.assertEqual(first_result["route_provenance"]["policy_profile"], "surface:telegram")
            self.assertEqual(first_result["route_provenance"]["selected_provider"], "openai_gpt54_chat")
            self.assertEqual(second_result["route_provenance"]["selected_model"], "gpt-5.4")

            stored = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertEqual([row["content"] for row in stored["chat-a"]], ["Need help with the repo", "Concrete Telegram reply."])
            self.assertEqual([row["content"] for row in stored["chat-b"]], ["Different chat", "Concrete Telegram reply."])


if __name__ == "__main__":
    unittest.main()
