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

    def test_telegram_surface_profile_overrides_capability_router_lane(self):
        policy = {
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
                "local_vllm_assistant": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "models": [{"id": "local-assistant", "maxInputChars": 200000}],
                },
                "grok_api": {
                    "enabled": True,
                    "paid": False,
                    "tier": "auth",
                    "type": "mock",
                    "models": [{"id": "grok-4-fast", "maxInputChars": 500000}],
                },
                "openai_gpt54_chat": {
                    "enabled": True,
                    "paid": False,
                    "tier": "auth",
                    "type": "mock",
                    "models": [{"id": "gpt-5.4", "maxInputChars": 500000}],
                },
            },
            "routing": {
                "free_order": ["local_vllm_assistant", "grok_api", "openai_gpt54_chat"],
                "intents": {
                    "conversation": {
                        "order": ["local_vllm_assistant", "grok_api", "openai_gpt54_chat"],
                        "allowPaid": True,
                    }
                },
                "capability_router": {
                    "enabled": True,
                    "mechanicalProvider": "local_vllm_assistant",
                    "chatProvider": "grok_api",
                    "planningProvider": "grok_api",
                    "reasoningProvider": "grok_api",
                    "subagentProvider": "local_vllm_assistant",
                    "codeProvider": "local_vllm_assistant",
                    "smallCodeProvider": "local_vllm_assistant",
                    "explicitTriggers": {},
                },
                "surface_profiles": {
                    "telegram": {
                        "capability_router": {
                            "chatProvider": "openai_gpt54_chat",
                            "planningProvider": "openai_gpt54_chat",
                            "reasoningProvider": "openai_gpt54_chat",
                            "codeProvider": "openai_gpt54_chat",
                            "smallCodeProvider": "openai_gpt54_chat",
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
                handlers={
                    "local_vllm_assistant": lambda payload, model_id, context: {"ok": True, "text": "local"},
                    "grok_api": lambda payload, model_id, context: {"ok": True, "text": "grok"},
                    "openai_gpt54_chat": lambda payload, model_id, context: {"ok": True, "text": "openai"},
                },
            )

            prompt = "plan architecture and evaluate trade-offs.\n" + ("- option\n" * 2500)
            default_out = router.execute_with_escalation(
                "conversation",
                {"prompt": prompt},
                {"input_text": prompt},
            )
            telegram_out = router.execute_with_escalation(
                "conversation",
                {"prompt": prompt},
                {"input_text": prompt, "surface": "telegram"},
            )

            self.assertTrue(default_out["ok"], default_out)
            self.assertEqual(default_out["provider"], "grok_api")
            self.assertTrue(telegram_out["ok"], telegram_out)
            self.assertEqual(telegram_out["provider"], "openai_gpt54_chat")
            self.assertEqual(telegram_out["route_provenance"]["policy_profile"], "surface:telegram")
            self.assertEqual(telegram_out["route_provenance"]["selected_model"], "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
