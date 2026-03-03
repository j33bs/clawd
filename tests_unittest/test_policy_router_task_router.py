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


def _policy(*, remote_enabled: bool, auth_daily_tokens: int = 999999):
    return {
        "version": 2,
        "defaults": {
            "allowPaid": True,
            "maxTokensPerRequest": 120000,
            "local_context_max_tokens_assistant": 32768,
            "local_context_max_tokens_coder": 32768,
            "local_context_soft_limit_tokens": 24576,
            "local_context_overflow_policy": "spill_remote",
            "remoteRoutingEnabled": remote_enabled,
            "remoteAllowlistTaskClasses": ["planning_synthesis", "research_browse", "code_generation_large"],
            "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
        },
        "budgets": {
            "intents": {"conversation": {"dailyTokenBudget": 999999, "dailyCallBudget": 999, "maxCallsPerRun": 20}},
            "tiers": {
                "free": {"dailyTokenBudget": 999999, "dailyCallBudget": 999},
                "auth": {"dailyTokenBudget": auth_daily_tokens, "dailyCallBudget": 999},
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
            "openai_gpt52_chat": {
                "enabled": True,
                "paid": False,
                "tier": "auth",
                "type": "mock",
                "models": [{"id": "gpt-5.2-chat-latest", "maxInputChars": 500000}],
            },
        },
        "routing": {
            "free_order": ["local_vllm_assistant", "openai_gpt52_chat"],
            "intents": {"conversation": {"order": ["local_vllm_assistant", "openai_gpt52_chat"], "allowPaid": True}},
            "capability_router": {
                "enabled": True,
                "mechanicalProvider": "local_vllm_assistant",
                "planningProvider": "openai_gpt52_chat",
                "reasoningProvider": "openai_gpt52_chat",
                "subagentProvider": "local_vllm_assistant",
                "codeProvider": "local_vllm_assistant",
                "smallCodeProvider": "local_vllm_assistant",
                "explicitTriggers": {},
            },
        },
    }


class PolicyRouterTaskRouterTests(unittest.TestCase):
    def _build_router(self, tmp: Path, policy: dict) -> PolicyRouter:
        policy_path = tmp / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        return PolicyRouter(
            policy_path=policy_path,
            budget_path=tmp / "budget.json",
            circuit_path=tmp / "circuit.json",
            event_log=tmp / "events.jsonl",
            handlers={
                "local_vllm_assistant": lambda payload, model_id, context: {"ok": True, "text": "local"},
                "openai_gpt52_chat": lambda payload, model_id, context: {"ok": True, "text": "remote"},
            },
        )

    def test_mechanical_short_routes_local(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td), _policy(remote_enabled=True))
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "apply patch to src/app.py and run tests"},
                {"input_text": "apply patch to src/app.py and run tests"},
            )
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "local_vllm_assistant")
            self.assertEqual(out["capability_class"], "mechanical_execution")

    def test_long_planning_within_limit_stays_local(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td), _policy(remote_enabled=True))
            prompt = "plan architecture and evaluate trade-offs.\n" + ("- option\n" * 2500)
            out = router.execute_with_escalation("conversation", {"prompt": prompt}, {"input_text": prompt})
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "local_vllm_assistant")
            self.assertEqual(out["capability_class"], "planning_synthesis")

    def test_overflow_uses_remote_only_when_enabled_and_budget_allows(self):
        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td), _policy(remote_enabled=True))
            prompt = "plan architecture deeply " + ("x" * 250000)
            with patch.dict(
                os.environ,
                {
                    "ENABLE_MURMURATION": "0",
                    "ENABLE_RESERVOIR": "0",
                    "ENABLE_PHYSARUM_ROUTER": "0",
                    "ENABLE_TRAIL_MEMORY": "0",
                    "TACTI_CR_ENABLE": "0",
                },
                clear=False,
            ):
                out = router.execute_with_escalation("conversation", {"prompt": prompt}, {"input_text": prompt})
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "openai_gpt52_chat")

        with tempfile.TemporaryDirectory() as td:
            router = self._build_router(Path(td), _policy(remote_enabled=True, auth_daily_tokens=5))
            prompt = "plan architecture deeply " + ("x" * 250000)
            with patch.dict(
                os.environ,
                {
                    "ENABLE_MURMURATION": "0",
                    "ENABLE_RESERVOIR": "0",
                    "ENABLE_PHYSARUM_ROUTER": "0",
                    "ENABLE_TRAIL_MEMORY": "0",
                    "TACTI_CR_ENABLE": "0",
                },
                clear=False,
            ):
                out = router.execute_with_escalation("conversation", {"prompt": prompt}, {"input_text": prompt})
            self.assertFalse(out["ok"])
            self.assertEqual(out["reason_code"], "context_too_large")
            self.assertEqual(out.get("error", {}).get("type"), "CONTEXT_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
