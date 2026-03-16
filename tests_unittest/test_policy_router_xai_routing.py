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

from policy_router import PolicyRouter  # noqa: E402


class PolicyRouterXaiRoutingTests(unittest.TestCase):
    def _policy(self):
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
                    "paid": {"dailyTokenBudget": 999999, "dailyCallBudget": 999},
                },
            },
            "providers": {
                "local_vllm_assistant": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "provider_id": "local_vllm",
                    "type": "mock",
                    "models": [{"id": "local-assistant", "maxInputChars": 200000}],
                },
                "grok_api": {
                    "enabled": True,
                    "paid": True,
                    "tier": "paid",
                    "type": "mock",
                    "apiKeyEnv": "GROK_API_KEY",
                    "models": [
                        {"id": "grok-4-1-fast", "maxInputChars": 12000, "tier": "chat"},
                        {"id": "grok-4-fast-reasoning", "maxInputChars": 24000, "tier": "reasoning"},
                        {"id": "grok-code-fast-1", "maxInputChars": 24000, "tier": "code"},
                    ],
                },
            },
            "routing": {
                "free_order": ["local_vllm_assistant"],
                "intents": {
                    "conversation": {
                        "order": ["local_vllm_assistant", "grok_api"],
                        "allowPaid": True,
                    }
                },
                "capability_router": {
                    "enabled": True,
                    "subagentProvider": "local_vllm_assistant",
                    "mechanicalProvider": "local_vllm_assistant",
                    "chatProvider": "grok_api",
                    "planningProvider": "grok_api",
                    "reasoningProvider": "grok_api",
                    "codeProvider": "grok_api",
                    "smallCodeProvider": "local_vllm_assistant",
                    "localChatMaxChars": 40,
                    "reasoningEscalationTokens": 50,
                    "structureComplexityMinBullets": 2,
                    "structureComplexityMinPaths": 2,
                    "explicitTriggers": {},
                },
            },
        }

    def _build_router(self, tmp: Path) -> PolicyRouter:
        policy_path = tmp / "policy.json"
        policy_path.write_text(json.dumps(self._policy()), encoding="utf-8")
        return PolicyRouter(
            policy_path=policy_path,
            budget_path=tmp / "budget.json",
            circuit_path=tmp / "circuit.json",
            event_log=tmp / "events.jsonl",
            handlers={
                "local_vllm_assistant": lambda payload, model_id, context: {"ok": True, "text": "local"},
                "grok_api": lambda payload, model_id, context: {"ok": True, "text": model_id},
            },
        )

    def test_short_chat_stays_local(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            sel = router.select_model("conversation", {"input_text": "hello"})
            self.assertEqual(sel["provider"], "local_vllm_assistant")
            self.assertEqual(sel["model"], "local-assistant")

    def test_long_chat_uses_grok_chat_lane(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            text = "Tell me a vivid but concise story about daily routines on a rainy Brisbane morning."
            sel = router.select_model("conversation", {"input_text": text})
            self.assertEqual(sel["provider"], "grok_api")
            self.assertEqual(sel["model"], "grok-4-1-fast")

    def test_planning_routes_to_grok_reasoning(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            text = "Plan the architecture.\n- compare /src/app.py\n- compare /src/router.py"
            sel = router.select_model("conversation", {"input_text": text})
            self.assertEqual(sel["provider"], "grok_api")
            self.assertEqual(sel["model"], "grok-4-fast-reasoning")

    def test_large_code_routes_to_grok_code_lane(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            text = "Implement code changes across modules in src/app.py and src/router.py"
            sel = router.select_model(
                "conversation",
                {"input_text": text, "expected_change_size": "large", "expected_loc": 300},
            )
            self.assertEqual(sel["provider"], "grok_api")
            self.assertEqual(sel["model"], "grok-code-fast-1")

    def test_xai_env_alias_satisfies_provider_gate(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td))
            with patch.dict(os.environ, {"XAI_API_KEY": "xai-test-token"}, clear=False):
                out = router.execute_with_escalation(
                    "conversation",
                    {"prompt": "Tell me a vivid but concise story about daily routines on a rainy Brisbane morning."},
                    {"input_text": "Tell me a vivid but concise story about daily routines on a rainy Brisbane morning."},
                )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "grok_api")
            self.assertEqual(out["model"], "grok-4-1-fast")


if __name__ == "__main__":
    unittest.main()
