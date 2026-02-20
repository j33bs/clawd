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

import policy_router  # noqa: E402
from proprioception import ProprioceptiveSampler  # noqa: E402


class TestRouterProprioception(unittest.TestCase):
    def _policy_path(self, root: Path) -> Path:
        payload = {
            "version": 2,
            "defaults": {
                "allowPaid": False,
                "maxTokensPerRequest": 2048,
                "circuitBreaker": {
                    "failureThreshold": 3,
                    "cooldownSec": 60,
                    "windowSec": 60,
                    "failOn": [],
                },
            },
            "budgets": {
                "intents": {
                    "coding": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000, "maxCallsPerRun": 20}
                },
                "tiers": {"free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}},
            },
            "providers": {
                "mock_provider": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "models": [{"id": "mock-model", "maxInputChars": 8000}],
                }
            },
            "routing": {
                "free_order": ["mock_provider"],
                "intents": {"coding": {"order": ["free"], "allowPaid": False}},
            },
        }
        path = root / "policy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_sampler_quantiles_deterministic(self):
        sampler = ProprioceptiveSampler(maxlen=10)
        for value in [10.0, 20.0, 30.0, 40.0]:
            sampler.record_decision(duration_ms=value, ok=True)
        snap = sampler.snapshot()
        self.assertEqual(snap["latency_ms_p50"], 25.0)
        self.assertEqual(snap["latency_ms_p95"], 38.5)
        self.assertEqual(snap["decisions_last_n"], 4)
        self.assertEqual(snap["error_rate"], 0.0)

    def test_router_flag_off_has_no_proprio_meta(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with patch.dict(
                os.environ,
                {"OPENCLAW_ROUTER_PROPRIOCEPTION": "0", "OPENCLAW_WITNESS_LEDGER": "0"},
                clear=False,
            ):
                router = policy_router.PolicyRouter(
                    policy_path=self._policy_path(tmp),
                    budget_path=tmp / "budget.json",
                    circuit_path=tmp / "circuit.json",
                    event_log=tmp / "events.jsonl",
                    handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                )
                result = router.execute_with_escalation("coding", {"prompt": "small patch"}, context_metadata={"agent_id": "main"})
        self.assertTrue(result["ok"])
        self.assertNotIn("meta", result)

    def test_router_flag_on_includes_proprio_meta_and_empty_breakers(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with patch.dict(
                os.environ,
                {"OPENCLAW_ROUTER_PROPRIOCEPTION": "1", "OPENCLAW_WITNESS_LEDGER": "0"},
                clear=False,
            ):
                router = policy_router.PolicyRouter(
                    policy_path=self._policy_path(tmp),
                    budget_path=tmp / "budget.json",
                    circuit_path=tmp / "circuit.json",
                    event_log=tmp / "events.jsonl",
                    handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                )
                result = router.execute_with_escalation("coding", {"prompt": "small patch"}, context_metadata={"agent_id": "main"})
        self.assertTrue(result["ok"])
        snap = result["meta"]["proprioception"]
        self.assertIn("latency_ms_p50", snap)
        self.assertIn("latency_ms_p95", snap)
        self.assertIn("decisions_last_n", snap)
        self.assertEqual(snap["breaker_open_providers"], [])


if __name__ == "__main__":
    unittest.main()
