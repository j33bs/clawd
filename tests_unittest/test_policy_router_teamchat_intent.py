import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import policy_router  # noqa: E402


class TestPolicyRouterTeamChatIntent(unittest.TestCase):
    def _policy_path(self, root: Path) -> Path:
        payload = {
            "version": 2,
            "defaults": {
                "allowPaid": False,
                "maxTokensPerRequest": 2048,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {
                    "coding": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000, "maxCallsPerRun": 20}
                },
                "tiers": {"free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}},
            },
            "providers": {
                "local_mock_provider": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "provider_id": "local_vllm",
                    "models": [{"id": "mock-model", "maxInputChars": 8000}],
                }
            },
            "routing": {
                "free_order": ["local_mock_provider"],
                "intents": {"coding": {"order": ["free"], "allowPaid": False}},
            },
        }
        path = root / "policy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_teamchat_intent_uses_coding_routing_and_budget_key(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            router = policy_router.PolicyRouter(
                policy_path=self._policy_path(tmp),
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={"local_mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
            )
            out = router.execute_with_escalation(
                "teamchat:planner",
                {"prompt": "Plan next steps"},
                context_metadata={"agent_id": "planner"},
            )

        self.assertTrue(out["ok"])
        self.assertEqual(out["provider"], "local_mock_provider")
        self.assertIn("coding", router.budget_state.get("intents", {}))
        self.assertNotIn("teamchat:planner", router.budget_state.get("intents", {}))


if __name__ == "__main__":
    unittest.main()
