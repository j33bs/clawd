import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from policy_router import PolicyRouter  # noqa: E402


class PolicyRouterKernelProvenanceTests(unittest.TestCase):
    def test_execute_with_escalation_carries_kernel_metadata_into_route_provenance(self):
        policy = {
            "version": 2,
            "defaults": {
                "allowPaid": True,
                "maxTokensPerRequest": 4096,
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
                "openai_gpt54_chat": {
                    "enabled": True,
                    "paid": False,
                    "tier": "auth",
                    "type": "mock",
                    "models": [{"id": "gpt-5.4"}],
                },
            },
            "routing": {
                "free_order": ["openai_gpt54_chat"],
                "intents": {
                    "conversation": {
                        "order": ["openai_gpt54_chat"],
                        "allowPaid": True,
                    }
                },
                "capability_router": {"enabled": False},
            },
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = PolicyRouter(
                policy_path=policy_path,
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={"openai_gpt54_chat": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
            )
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "hello"},
                {
                    "input_text": "hello",
                    "surface": "telegram",
                    "kernel_id": "c_lawd:surface:telegram",
                    "kernel_hash": "a" * 64,
                    "surface_overlay": "surface:telegram|mode:conversation|memory:on",
                },
            )

            self.assertTrue(out["ok"], out)
            self.assertEqual(out["route_provenance"]["kernel_id"], "c_lawd:surface:telegram")
            self.assertEqual(out["route_provenance"]["kernel_hash"], "a" * 64)
            self.assertEqual(out["route_provenance"]["surface_overlay"], "surface:telegram|mode:conversation|memory:on")


if __name__ == "__main__":
    unittest.main()
