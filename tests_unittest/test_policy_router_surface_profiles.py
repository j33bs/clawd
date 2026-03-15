import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from policy_router import PolicyRouter  # noqa: E402


class PolicyRouterSurfaceProfilesTests(unittest.TestCase):
    def test_telegram_surface_profile_overrides_global_conversation_order(self):
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
                "local_vllm_assistant": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "models": [{"id": "local-assistant"}],
                },
                "openai_gpt54_chat": {
                    "enabled": True,
                    "paid": False,
                    "tier": "auth",
                    "type": "mock",
                    "models": [{"id": "gpt-5.4"}],
                },
            },
            "routing": {
                "free_order": ["local_vllm_assistant"],
                "intents": {
                    "conversation": {
                        "order": ["local_vllm_assistant", "openai_gpt54_chat"],
                        "allowPaid": True,
                    }
                },
                "capability_router": {"enabled": False},
                "surface_profiles": {
                    "telegram": {
                        "intents": {
                            "conversation": {
                                "order": ["openai_gpt54_chat", "local_vllm_assistant"],
                                "allowPaid": True,
                            }
                        }
                    }
                },
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
                handlers={},
            )

            default_choice = router.select_model("conversation", {"input_text": "hello"})
            telegram_choice = router.select_model("conversation", {"input_text": "hello", "surface": "telegram"})
            telegram_explain = router.explain_route("conversation", {"input_text": "hello", "surface": "telegram"})

            self.assertEqual(default_choice["provider"], "local_vllm_assistant")
            self.assertEqual(telegram_choice["provider"], "openai_gpt54_chat")
            self.assertEqual(telegram_explain["surface"], "telegram")
            self.assertEqual(telegram_explain["policy_profile"], "surface:telegram")
            self.assertEqual(telegram_explain["chosen"]["provider"], "openai_gpt54_chat")


if __name__ == "__main__":
    unittest.main()
