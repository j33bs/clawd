import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import policy_router  # noqa: E402


def _policy(tmp: Path, order, max_tokens=256):
    policy_path = tmp / "policy.json"
    policy = {
        "version": 2,
        "defaults": {"allowPaid": True, "maxTokensPerRequest": max_tokens},
        "budgets": {
            "intents": {"itc_classify": {"dailyTokenBudget": 999999, "dailyCallBudget": 9999, "maxCallsPerRun": 10}},
            "tiers": {"free": {"dailyTokenBudget": 999999, "dailyCallBudget": 9999}},
        },
        "providers": {
            "local_vllm_assistant": {"enabled": True, "tier": "free", "models": [{"id": "local-model", "maxInputChars": 4000}]},
            "cloud_provider": {"enabled": True, "tier": "free", "models": [{"id": "cloud-model", "maxInputChars": 4000}]},
        },
        "routing": {"free_order": [], "intents": {"itc_classify": {"order": order, "allowPaid": True, "maxTokensPerRequest": max_tokens}}},
    }
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return policy_path


class TestPolicyRouterGlueIntegrations(unittest.TestCase):
    def test_metrics_gate_prunes_local_and_halves_tokens(self):
        with patch.object(policy_router, "read_metrics_artifact", return_value={"routing": {"queue_depth": 4, "kv_cache_usage_pct": 90}}):
            order, tokens, details = policy_router._apply_metrics_gates(["local_vllm_assistant", "cloud_provider"], 256)
        self.assertEqual(order, ["cloud_provider"])
        self.assertEqual(tokens, 128)
        self.assertEqual(details["queue_depth"], 4)

    def test_reservoir_urgency_moves_local_vllm_first(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            router = policy_router.PolicyRouter(
                policy_path=_policy(tmp, ["cloud_provider", "local_vllm_assistant"]),
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={
                    "local_vllm_assistant": lambda payload, model_id, ctx: {"ok": True, "text": "local"},
                    "cloud_provider": lambda payload, model_id, ctx: {"ok": True, "text": "cloud"},
                },
            )
            with patch.object(policy_router, "_reservoir_readout", return_value={"routing_hints": {"urgency": 0.95}}):
                result = router.execute_with_escalation("itc_classify", {"prompt": "hello"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "local_vllm_assistant")

    def test_itc_signal_risk_off_moves_cloud_first(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            router = policy_router.PolicyRouter(
                policy_path=_policy(tmp, ["local_vllm_assistant", "cloud_provider"]),
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={
                    "local_vllm_assistant": lambda payload, model_id, ctx: {"ok": True, "text": "local"},
                    "cloud_provider": lambda payload, model_id, ctx: {"ok": True, "text": "cloud"},
                },
            )
            signal = {"reason": "ok", "signal": {"metrics": {"risk_on": 0.1, "risk_off": 0.9}}}
            with patch.object(policy_router, "get_itc_signal", return_value=signal), patch.object(policy_router, "_reservoir_readout", return_value=None):
                result = router.execute_with_escalation("itc_classify", {"prompt": "hello"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "cloud_provider")

    def test_tacti_arousal_factor_caps_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            router = policy_router.PolicyRouter(
                policy_path=_policy(tmp, ["local_vllm_assistant"], max_tokens=200),
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={"local_vllm_assistant": lambda payload, model_id, ctx: {"ok": True, "text": "local"}},
            )
            long_prompt = "A" * 500
            with patch.object(policy_router, "_reservoir_readout", return_value=None), patch.object(
                policy_router,
                "_tacti_main_flow_enhance_plan",
                return_value=(["local_vllm_assistant"], {"arousal_suppression_factor": 0.3}),
            ):
                result = router.execute_with_escalation("itc_classify", {"prompt": long_prompt})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "request_token_cap_exceeded")


if __name__ == "__main__":
    unittest.main()
