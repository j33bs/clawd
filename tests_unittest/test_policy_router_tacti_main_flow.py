import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import policy_router  # noqa: E402


class TestPolicyRouterTactiMainFlow(unittest.TestCase):
    def test_flags_off_preserves_flow_without_tacti_hook_invocation(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            budget = tmp / "budget.json"
            circuit = tmp / "circuit.json"
            events = tmp / "events.jsonl"

            env = {
                "ENABLE_MURMURATION": "0",
                "ENABLE_RESERVOIR": "0",
                "ENABLE_PHYSARUM_ROUTER": "0",
                "ENABLE_TRAIL_MEMORY": "0",
                "GEMINI_API_KEY": "dummy-key",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(
                    policy_router,
                    "tacti_enhance_plan",
                    side_effect=AssertionError("tacti_enhance_plan should not be called when flags are off"),
                ):
                    router = policy_router.PolicyRouter(
                        budget_path=budget,
                        circuit_path=circuit,
                        event_log=events,
                        handlers={"google-gemini-cli": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                    )
                    result = router.execute_with_escalation(
                        "itc_classify",
                        {"prompt": "quick classify"},
                        context_metadata={"input_text": "quick classify", "agent_id": "main"},
                    )

            self.assertTrue(result["ok"])
            self.assertIsNone(result.get("tacti"))

    def test_flag_on_runs_tacti_hook_and_records_non_empty_agent_ids(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            budget = tmp / "budget.json"
            circuit = tmp / "circuit.json"
            events = tmp / "events.jsonl"

            env = {
                "ENABLE_MURMURATION": "1",
                "ENABLE_RESERVOIR": "0",
                "ENABLE_PHYSARUM_ROUTER": "0",
                "ENABLE_TRAIL_MEMORY": "0",
                "GEMINI_API_KEY": "dummy-key",
            }
            with patch.dict(os.environ, env, clear=False):
                router = policy_router.PolicyRouter(
                    budget_path=budget,
                    circuit_path=circuit,
                    event_log=events,
                    handlers={"google-gemini-cli": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                )
                result = router.execute_with_escalation(
                    "itc_classify",
                    {"prompt": "quick classify"},
                    context_metadata={"input_text": "quick classify", "agent_id": "main", "session_id": "sess-1"},
                )

            self.assertTrue(result["ok"])
            self.assertIsInstance(result.get("tacti"), dict)
            self.assertTrue(result["tacti"].get("enabled"))
            self.assertTrue(result["tacti"].get("agent_ids"))
            self.assertIn(result.get("provider"), result["tacti"].get("agent_ids", []))

            events_payload = []
            if events.exists():
                for line in events.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    events_payload.append(json.loads(line))
            self.assertTrue(any(item.get("event") == "tacti_routing_plan" for item in events_payload))

    def test_flags_off_does_not_create_tacti_runtime_events_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            budget = tmp / "budget.json"
            circuit = tmp / "circuit.json"
            events = tmp / "events.jsonl"
            runtime_events = tmp / "state_runtime" / "tacti_cr" / "events.jsonl"

            env = {
                "ENABLE_MURMURATION": "0",
                "ENABLE_RESERVOIR": "0",
                "ENABLE_PHYSARUM_ROUTER": "0",
                "ENABLE_TRAIL_MEMORY": "0",
                "TACTI_CR_ENABLE": "0",
                "TACTI_CR_EVENTS_PATH": str(runtime_events),
                "GEMINI_API_KEY": "dummy-key",
            }
            with patch.dict(os.environ, env, clear=False):
                router = policy_router.PolicyRouter(
                    budget_path=budget,
                    circuit_path=circuit,
                    event_log=events,
                    handlers={"google-gemini-cli": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                )
                result = router.execute_with_escalation(
                    "itc_classify",
                    {"prompt": "quick classify"},
                    context_metadata={"input_text": "quick classify", "agent_id": "main"},
                )

            self.assertTrue(result["ok"])
            self.assertFalse(runtime_events.exists())


if __name__ == "__main__":
    unittest.main()
