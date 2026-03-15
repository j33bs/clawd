import asyncio
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "message_handler.py"


def _load_message_handler_module():
    spec = importlib.util.spec_from_file_location("message_handler", str(MODULE_PATH))
    assert spec and spec.loader, f"Failed to load module spec for {MODULE_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _DummyRouter:
    def __init__(self) -> None:
        self.calls = []

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        self.calls.append(
            {
                "intent": intent,
                "payload": payload,
                "context_metadata": dict(context_metadata or {}),
                "validate_fn": validate_fn,
            }
        )
        return {
            "ok": True,
            "provider": "minimax_m25",
            "model": "minimax-portal/MiniMax-M2.5",
            "text": "Shared router reply",
            "reason_code": "success",
            "request_id": "req-123",
        }


class TestMessageHandler(unittest.TestCase):
    def test_handle_incoming_message_uses_shared_router_stack(self):
        message_handler = _load_message_handler_module()
        router = _DummyRouter()
        handler = message_handler.MessageHandler("http://127.0.0.1:18789", "token", router=router)
        message = {
            "message_id": "2002",
            "chat_id": "8159253715",
            "chat_title": "jeebs",
            "author_name": "jeebs",
            "reply_to_message_id": "2001",
            "content": "use minimax and tell me what's live",
        }

        with mock.patch.object(
            message_handler,
            "telegram_memory_context_text",
            return_value=[
                "- 2026-03-15 assistant [reply-to 2001]: I'll align Telegram with the shared router."
            ],
        ):
            with mock.patch.object(message_handler, "user_context_packet_text", return_value=["- Keep it concise."]):
                with mock.patch.object(message_handler, "source_context_packet_text", return_value=["- Open work: Telegram alignment"]):
                    with mock.patch.object(message_handler, "build_recall_block", return_value="TELEGRAM_RECALL:\n- semantic note"):
                        with mock.patch.object(message_handler, "route_metadata_for_text", return_value={"preferred_provider": "minimax_m25"}):
                            with mock.patch.object(message_handler, "build_telegram_chat_prompt", return_value="PROMPT") as build_prompt:
                                with mock.patch.object(
                                    message_handler,
                                    "send_telegram_reply",
                                    new=mock.AsyncMock(return_value={"message_id": "3003"}),
                                ) as send_reply:
                                    with mock.patch.object(message_handler, "ingest_telegram_exchange") as ingest_memory:
                                        result = asyncio.run(message_handler.handle_incoming_message(message, handler))

        self.assertTrue(result["success"])
        self.assertEqual(result["route"], "minimax_m25")
        self.assertEqual(result["model"], "minimax-portal/MiniMax-M2.5")
        self.assertEqual(router.calls[0]["intent"], "conversation")
        self.assertEqual(router.calls[0]["payload"]["messages"][0]["content"], "PROMPT")
        self.assertEqual(router.calls[0]["context_metadata"]["surface"], "telegram")
        self.assertEqual(router.calls[0]["context_metadata"]["preferred_provider"], "minimax_m25")
        self.assertEqual(router.calls[0]["context_metadata"]["thread_message_id"], "2001")
        build_prompt.assert_called_once()
        send_reply.assert_awaited_once()
        ingest_memory.assert_called_once()
        self.assertEqual(ingest_memory.call_args.kwargs["role"], "assistant")
        self.assertEqual(ingest_memory.call_args.kwargs["meta"]["router_provider"], "minimax_m25")


if __name__ == "__main__":
    unittest.main()
