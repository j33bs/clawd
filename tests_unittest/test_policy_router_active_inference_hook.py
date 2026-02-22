import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import policy_router  # noqa: E402


class TestPolicyRouterActiveInferenceHook(unittest.TestCase):
    def _policy_path(self, root: Path) -> Path:
        payload = {
            "version": 2,
            "defaults": {
                "allowPaid": False,
                "maxTokensPerRequest": 2048,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {"coding": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000, "maxCallsPerRun": 20}},
                "tiers": {"free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}},
            },
            "providers": {
                "groq": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "g"}]},
                "local_vllm_assistant": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "l"}]},
            },
            "routing": {
                "free_order": ["groq", "local_vllm_assistant"],
                "intents": {"coding": {"order": ["free"], "allowPaid": False}},
                "capability_router": {"enabled": True, "explicitTriggers": {}},
            },
        }
        path = root / "policy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_active_inference_predict_and_update_in_execute(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            budget = tmp / "budget.json"
            circuit = tmp / "circuit.json"
            events = tmp / "events.jsonl"
            ai_state = tmp / "active_inference_state.json"
            captured = {}

            def _handler(payload, model_id, context_metadata):
                captured["context_metadata"] = dict(context_metadata)
                return {"ok": True, "text": "- concise bullet output"}

            env = {
                "ENABLE_ACTIVE_INFERENCE": "1",
                "GROQ_API_KEY": "test-key",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(policy_router, "ACTIVE_INFERENCE_STATE_PATH", ai_state):
                    router = policy_router.PolicyRouter(
                        budget_path=budget,
                        circuit_path=circuit,
                        event_log=events,
                        handlers={"groq": _handler},
                    )
                    result = router.execute_with_escalation(
                        "governance",
                        {"prompt": "be concise and structured"},
                        context_metadata={
                            "input_text": "be concise and structured",
                            "feedback": {"liked": True},
                            "requires_tools": False,
                        },
                    )

            self.assertTrue(result["ok"])
            self.assertIn("active_inference", captured["context_metadata"])
            ai = captured["context_metadata"]["active_inference"]
            self.assertIn("preference_params", ai)
            self.assertIn("confidence", ai)
            self.assertTrue(ai_state.exists())

    def test_openclaw_active_inference_prefers_local_provider_for_concise_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with patch.dict(os.environ, {"OPENCLAW_ACTIVE_INFERENCE": "1"}, clear=False):
                router = policy_router.PolicyRouter(
                    policy_path=self._policy_path(tmp),
                    budget_path=tmp / "budget.json",
                    circuit_path=tmp / "circuit.json",
                    event_log=tmp / "events.jsonl",
                    handlers={
                        "groq": lambda payload, model_id, context_metadata: {"ok": True, "text": "groq"},
                        "local_vllm_assistant": lambda payload, model_id, context_metadata: {"ok": True, "text": "local"},
                    },
                )
                result = router.execute_with_escalation(
                    "coding",
                    {"prompt": "small patch"},
                    context_metadata={"input_text": "be concise and brief", "requires_tools": False},
                )
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "local_vllm_assistant")

    def test_active_inference_fallback_keeps_router_operational(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with patch.dict(os.environ, {"OPENCLAW_ACTIVE_INFERENCE": "1"}, clear=False):
                with patch.object(policy_router, "ActiveInferenceAgent", side_effect=RuntimeError("boom")):
                    router = policy_router.PolicyRouter(
                        policy_path=self._policy_path(tmp),
                        budget_path=tmp / "budget.json",
                        circuit_path=tmp / "circuit.json",
                        event_log=tmp / "events.jsonl",
                        handlers={"groq": lambda payload, model_id, context_metadata: {"ok": True, "text": "groq"}},
                    )
                    result = router.execute_with_escalation(
                        "coding",
                        {"prompt": "small patch"},
                        context_metadata={"input_text": "normal task"},
                    )
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
