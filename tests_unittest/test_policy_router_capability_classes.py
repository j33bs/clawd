import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from policy_router import PolicyRouter, classify_intent


class TestPolicyRouterCapabilityClasses(unittest.TestCase):
    def _build_router(self, tmp: Path) -> PolicyRouter:
        policy = {
            "version": 2,
            "defaults": {
                "allowPaid": True,
                "maxTokensPerRequest": 2048,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {"conversation": {"dailyTokenBudget": 999999, "dailyCallBudget": 999, "maxCallsPerRun": 20}},
                "tiers": {
                    "free": {"dailyTokenBudget": 999999, "dailyCallBudget": 999},
                    "auth": {"dailyTokenBudget": 999999, "dailyCallBudget": 999},
                },
            },
            "providers": {
                "local_vllm_assistant": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "models": [{"id": "vllm/local-assistant", "maxInputChars": 4000}],
                },
                "openai_gpt52_chat": {
                    "enabled": True,
                    "paid": False,
                    "tier": "auth",
                    "type": "mock",
                    "models": [{"id": "gpt-5.2-chat-latest", "maxInputChars": 4000}],
                },
            },
            "routing": {
                "free_order": ["local_vllm_assistant", "openai_gpt52_chat"],
                "intents": {
                    "conversation": {
                        "order": ["local_vllm_assistant", "openai_gpt52_chat"],
                        "allowPaid": True,
                    }
                },
                "capability_router": {
                    "enabled": True,
                    "mechanicalProvider": "local_vllm_assistant",
                    "planningProvider": "openai_gpt52_chat",
                    "subagentProvider": "local_vllm_assistant",
                    "explicitTriggers": {},
                },
            },
        }
        policy_path = tmp / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        return PolicyRouter(
            policy_path=policy_path,
            budget_path=tmp / "budget.json",
            circuit_path=tmp / "circuit.json",
            event_log=tmp / "events.jsonl",
            handlers={
                "local_vllm_assistant": lambda payload, model_id, context: {"ok": True, "text": "local"},
                "openai_gpt52_chat": lambda payload, model_id, context: {"ok": True, "text": "cloud"},
            },
        )

    def test_mechanical_execution_prefers_local_vllm(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            sel = router.select_model("conversation", {"input_text": "run tests and refactor src/app.py"})
            self.assertEqual(sel["provider"], "local_vllm_assistant", sel)

    def test_planning_synthesis_prefers_cloud(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            sel = router.select_model("conversation", {"input_text": "plan architecture and evaluate trade-offs"})
            self.assertEqual(sel["provider"], "openai_gpt52_chat", sel)

    def test_router_logs_request_id_latency_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            router = self._build_router(tmp)
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "run tests in repo"},
                context_metadata={"request_id": "req-test-1", "input_text": "run tests in repo"},
            )
            self.assertTrue(out["ok"], out)
            rows = (tmp / "events.jsonl").read_text(encoding="utf-8").splitlines()
            parsed = [json.loads(line) for line in rows if line.strip()]
            success_rows = [item for item in parsed if item.get("event") == "router_success"]
            self.assertTrue(success_rows)
            detail = success_rows[-1]["detail"]
            self.assertEqual(detail.get("request_id"), "req-test-1")
            self.assertIn("latency_ms", detail)
            self.assertEqual(detail.get("outcome_class"), "success")

    def test_classifier_negative_guards_prevent_overcapture(self):
        self.assertEqual(classify_intent("Explain the error code tg-mlwxbc23-00a"), "planning_synthesis")
        self.assertEqual(classify_intent("Discuss the code of ethics for agents"), "planning_synthesis")
        self.assertEqual(classify_intent("What is the patch schedule for security?"), "planning_synthesis")

    def test_classifier_mechanical_examples(self):
        self.assertEqual(classify_intent("Write code to parse jsonl"), "mechanical_execution")
        self.assertEqual(classify_intent("Apply this patch to the repo"), "mechanical_execution")
        self.assertEqual(classify_intent("Explain this code and apply the patch"), "mechanical_execution")

    def test_explain_and_apply_patch_routes_to_mechanical_provider(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            sel = router.select_model("conversation", {"input_text": "Explain this code and apply the patch"})
            self.assertEqual(sel["provider"], "local_vllm_assistant", sel)


if __name__ == "__main__":
    unittest.main()
