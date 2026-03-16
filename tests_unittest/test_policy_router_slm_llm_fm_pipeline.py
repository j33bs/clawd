import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from policy_router import PolicyRouter  # noqa: E402


def _policy():
    return {
        "version": 2,
        "defaults": {
            "allowPaid": True,
            "maxTokensPerRequest": 120000,
            "local_context_max_tokens_assistant": 32768,
            "local_context_max_tokens_coder": 32768,
            "local_context_soft_limit_tokens": 24576,
            "local_context_overflow_policy": "spill_remote",
            "remoteRoutingEnabled": True,
            "remoteAllowlistTaskClasses": ["planning_synthesis", "research_browse", "code_generation_large"],
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
            "slm_lane": {
                "enabled": True,
                "paid": False,
                "tier": "free",
                "type": "mock",
                "models": [{"id": "slm-model", "maxInputChars": 200000}],
            },
            "llm_lane": {
                "enabled": True,
                "paid": False,
                "tier": "free",
                "type": "mock",
                "models": [{"id": "llm-model", "maxInputChars": 200000}],
            },
            "fm_lane": {
                "enabled": True,
                "paid": False,
                "tier": "auth",
                "type": "mock",
                "models": [{"id": "fm-model", "maxInputChars": 500000}],
            },
        },
        "routing": {
            "free_order": ["slm_lane", "llm_lane", "fm_lane"],
            "intents": {"conversation": {"order": ["slm_lane", "llm_lane", "fm_lane"], "allowPaid": True}},
            "capability_router": {
                "enabled": True,
                "subagentProvider": "slm_lane",
                "mechanicalProvider": "llm_lane",
                "planningProvider": "fm_lane",
                "reasoningProvider": "fm_lane",
                "codeProvider": "llm_lane",
                "smallCodeProvider": "slm_lane",
                "explicitTriggers": {},
                "pipeline": {
                    "enabled": True,
                    "slmProvider": "slm_lane",
                    "llmProvider": "llm_lane",
                    "fmProvider": "fm_lane",
                    "smallTaskMaxTokens": 1200,
                    "smallTaskMaxLoc": 50,
                },
            },
        },
    }


class PolicyRouterPipelineTests(unittest.TestCase):
    def _build_router(self, tmp: Path) -> PolicyRouter:
        policy_path = tmp / "policy.json"
        policy_path.write_text(json.dumps(_policy()), encoding="utf-8")
        return PolicyRouter(
            policy_path=policy_path,
            budget_path=tmp / "budget.json",
            circuit_path=tmp / "circuit.json",
            event_log=tmp / "events.jsonl",
            handlers={
                "slm_lane": lambda payload, model_id, context: {"ok": True, "text": "slm"},
                "llm_lane": lambda payload, model_id, context: {"ok": True, "text": "llm"},
                "fm_lane": lambda payload, model_id, context: {"ok": True, "text": "fm"},
            },
        )

    def test_small_mechanical_work_uses_slm_lane(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "apply patch to src/app.py"},
                {"input_text": "apply patch to src/app.py", "expected_change_size": "small", "expected_loc": 20},
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "slm_lane")
            self.assertEqual(out["pipeline_stage"], "slm")

    def test_planning_work_within_budget_uses_llm_lane(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "plan architecture and evaluate trade-offs"},
                {"input_text": "plan architecture and evaluate trade-offs"},
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "llm_lane")
            self.assertEqual(out["pipeline_stage"], "llm")
            explain = router.explain_route(
                "conversation",
                {"input_text": "plan architecture and evaluate trade-offs"},
            )
            self.assertEqual(explain["pipeline_stage"], "llm", explain)

    def test_research_browse_routes_directly_to_fm_lane(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "browse the web for sources and cite links"},
                {"input_text": "browse the web for sources and cite links"},
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "fm_lane")
            self.assertEqual(out["pipeline_stage"], "fm")

    def test_planning_overflow_escalates_to_fm_lane(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            prompt = "plan architecture deeply " + ("x" * 250000)
            out = router.execute_with_escalation("conversation", {"prompt": prompt}, {"input_text": prompt})
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "fm_lane")
            self.assertEqual(out["pipeline_stage"], "fm")


if __name__ == "__main__":
    unittest.main()
