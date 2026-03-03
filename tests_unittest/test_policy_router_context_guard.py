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


def _base_policy(overflow_policy: str = "compress", remote_enabled: bool = False):
    return {
        "version": 2,
        "defaults": {
            "allowPaid": True,
            "maxTokensPerRequest": 40000,
            "local_context_max_tokens_assistant": 32768,
            "local_context_max_tokens_coder": 32768,
            "local_context_soft_limit_tokens": 24576,
            "local_context_overflow_policy": overflow_policy,
            "remoteRoutingEnabled": remote_enabled,
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
                "provider_id": "local_vllm",
                "type": "mock",
                "models": [{"id": "local-assistant", "maxInputChars": 200000}],
            },
            "openai_gpt52_chat": {
                "enabled": True,
                "paid": False,
                "tier": "auth",
                "type": "mock",
                "models": [{"id": "gpt-5.2-chat-latest", "maxInputChars": 30000}],
            },
        },
        "routing": {
            "free_order": ["local_vllm_assistant", "openai_gpt52_chat"],
            "intents": {"conversation": {"order": ["local_vllm_assistant", "openai_gpt52_chat"], "allowPaid": True}},
            "capability_router": {
                "enabled": True,
                "mechanicalProvider": "local_vllm_assistant",
                "planningProvider": "openai_gpt52_chat",
                "subagentProvider": "local_vllm_assistant",
                "codeProvider": "local_vllm_assistant",
                "smallCodeProvider": "local_vllm_assistant",
                "explicitTriggers": {},
            },
        },
    }


class PolicyRouterContextGuardTests(unittest.TestCase):
    def _build_router(self, tmp: Path, policy: dict, captured: dict) -> PolicyRouter:
        policy_path = tmp / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        return PolicyRouter(
            policy_path=policy_path,
            budget_path=tmp / "budget.json",
            circuit_path=tmp / "circuit.json",
            event_log=tmp / "events.jsonl",
            handlers={
                "local_vllm_assistant": lambda payload, model_id, context: captured.update({"payload": payload}) or {"ok": True, "text": "local"},
                "openai_gpt52_chat": lambda payload, model_id, context: {"ok": True, "text": "remote"},
            },
        )

    def test_16k_equivalent_input_no_longer_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            captured = {}
            router = self._build_router(tmp, _base_policy(), captured)
            payload = {"prompt": "a" * 64000}  # ~16k tokens estimate
            out = router.execute_with_escalation("conversation", payload, {"input_text": payload["prompt"]})
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["provider"], "local_vllm_assistant")
            self.assertIn("payload", captured)

    def test_context_guard_compresses_deterministically_over_soft_limit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            captured = {}
            policy = _base_policy(overflow_policy="compress")
            router = self._build_router(tmp, policy, captured)
            env_log = tmp / "events" / "gate_health.jsonl"
            payload = {"prompt": "# Header\n" + ("- item\n" * 18000) + "\n```python\nprint('x')\n```\n"}
            with patch.dict(os.environ, {"OPENCLAW_EVENT_ENVELOPE_LOG_PATH": str(env_log)}, clear=False):
                out = router.execute_with_escalation("conversation", payload, {"input_text": payload["prompt"]})
            self.assertTrue(out["ok"], out)
            compressed_prompt = str(captured.get("payload", {}).get("prompt", ""))
            self.assertLess(len(compressed_prompt), len(payload["prompt"]))
            lines = env_log.read_text(encoding="utf-8").splitlines()
            events = [json.loads(line) for line in lines if line.strip()]
            self.assertTrue(any(e.get("event") == "context.compressed" for e in events), events)

    def test_overflow_spill_remote_disabled_returns_structured_context_too_large(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            captured = {}
            policy = _base_policy(overflow_policy="spill_remote", remote_enabled=False)
            router = self._build_router(tmp, policy, captured)
            huge = "z" * 250000  # exceeds hard * 1.2 path
            out = router.execute_with_escalation("conversation", {"prompt": huge}, {"input_text": huge})
            self.assertFalse(out["ok"])
            self.assertEqual(out["reason_code"], "context_too_large")
            self.assertEqual(out.get("error", {}).get("type"), "CONTEXT_TOO_LARGE")
            self.assertIn("remediation", out.get("error", {}))


if __name__ == "__main__":
    unittest.main()
