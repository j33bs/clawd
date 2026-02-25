import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from team_chat_adapters import RouterLLMClient  # noqa: E402


class _FakeRouter:
    def __init__(self, text: str, parsed=None):
        self._text = text
        self._parsed = parsed

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        parsed = self._parsed
        if parsed is None and callable(validate_fn):
            parsed = validate_fn(self._text)
        return {"ok": True, "provider": "fake", "model": "fake/model", "reason_code": "ok", "text": self._text, "parsed": parsed}

    def explain_route(self, intent, context_metadata=None, payload=None):
        return {"intent": intent, "mode": "test"}


class TestTeamChatPauseGate(unittest.TestCase):
    def _make_client(self, text: str):
        client = RouterLLMClient.__new__(RouterLLMClient)
        client.repo_root = REPO_ROOT
        client.router = _FakeRouter(text=text)
        return client

    def test_response_path_unchanged_when_flag_off(self):
        os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        client = self._make_client('{"plan": {"summary":"s", "risk_level":"low"}, "work_orders": [{"id":"1","title":"t","goal":"g"}]}')

        out = client.run_json(
            intent="coding",
            input_text="task",
            trigger_phrase="use chatgpt",
            prompt="prompt",
            max_tokens=100,
            validate_fn=lambda t: __import__("json").loads(t),
        )
        self.assertTrue(out.ok)
        self.assertEqual(out.data["plan"]["risk_level"], "low")
        self.assertFalse(out.route["pause_check"]["enabled"])

    def test_response_path_pauses_when_enabled_and_filler(self):
        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        os.environ["OPENCLAW_PAUSE_CHECK_TEST_MODE"] = "1"
        try:
            filler = "Great question. Let's dive in. Generally speaking, it depends. " * 6
            client = self._make_client(filler)
            out = client.run_json(
                intent="coding",
                input_text="ok",
                trigger_phrase="use chatgpt",
                prompt="prompt",
                max_tokens=100,
                validate_fn=lambda t: None,
            )
            self.assertFalse(out.ok)
            self.assertEqual(out.error, "paused_no_value_add")
            self.assertEqual(out.route["pause_check"]["decision"], "silence")
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
            os.environ.pop("OPENCLAW_PAUSE_CHECK_TEST_MODE", None)


if __name__ == "__main__":
    unittest.main()
