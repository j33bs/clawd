from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


def _load_policy_router_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "policy_router.py"
    spec = importlib.util.spec_from_file_location("policy_router", str(mod_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestPolicyRouterTactiNovel10(unittest.TestCase):
    def test_arousal_and_expression_can_gate_heavy_escalation(self):
        policy_router = _load_policy_router_module()
        old_env = dict(os.environ)
        try:
            os.environ["TACTI_CR_ENABLE"] = "1"
            os.environ["TACTI_CR_AROUSAL_OSC"] = "1"
            os.environ["TACTI_CR_EXPRESSION_ROUTER"] = "1"
            os.environ["TACTI_CR_AROUSAL_SUPPRESS_THRESHOLD"] = "0.99"

            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td)
                policy = {
                    "version": 2,
                    "defaults": {"allowPaid": True, "maxTokensPerRequest": 2048, "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []}},
                    "budgets": {
                        "intents": {"coding": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000, "maxCallsPerRun": 10}},
                        "tiers": {"free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}, "auth": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}},
                    },
                    "providers": {
                        "openai_gpt52_chat": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "gpt-5.2-chat-latest"}]},
                        "local_vllm_assistant": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "vllm/local-assistant"}]},
                    },
                    "routing": {
                        "free_order": ["local_vllm_assistant"],
                        "intents": {"coding": {"order": ["openai_gpt52_chat", "local_vllm_assistant"], "allowPaid": True}},
                        "capability_router": {
                            "enabled": True,
                            "explicitTriggers": {"use chatgpt": "openai_gpt52_chat"},
                        },
                    },
                    "tacti_cr": {"flags": {"expression_router": True}},
                }
                policy_path = tmp / "policy.json"
                policy_path.write_text(json.dumps(policy), encoding="utf-8")

                router = policy_router.PolicyRouter(
                    policy_path=policy_path,
                    budget_path=tmp / "budget.json",
                    circuit_path=tmp / "circuit.json",
                    event_log=tmp / "events.jsonl",
                    handlers={"openai_gpt52_chat": lambda p, m, c: {"ok": True, "text": "ok"}, "local_vllm_assistant": lambda p, m, c: {"ok": True, "text": "ok"}},
                )
                result = router.execute_with_escalation(
                    "coding",
                    {"prompt": "small request"},
                    context_metadata={"input_text": "use chatgpt please", "agent_id": "main"},
                )
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["provider"], "local_vllm_assistant", result)
        finally:
            os.environ.clear()
            os.environ.update(old_env)


if __name__ == "__main__":
    unittest.main()
