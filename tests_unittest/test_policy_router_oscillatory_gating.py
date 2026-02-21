import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import policy_router  # noqa: E402


class _OscillatorStub:
    explain_called = 0

    def __init__(self, repo_root=None):
        self.repo_root = repo_root

    def explain(self, _dt):
        _OscillatorStub.explain_called += 1
        return {"multiplier": 0.73}

    def should_suppress_heavy_escalation(self):
        return False


class TestPolicyRouterOscillatoryGating(unittest.TestCase):
    def _policy_path(self, root: Path) -> Path:
        payload = {
            "version": 2,
            "defaults": {"allowPaid": False, "maxTokensPerRequest": 2048, "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []}},
            "budgets": {"intents": {"coding": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000, "maxCallsPerRun": 10}}, "tiers": {"free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}}},
            "providers": {"mock_provider": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "mock-model", "maxInputChars": 8000}]}},
            "routing": {"free_order": ["mock_provider"], "intents": {"coding": {"order": ["free"], "allowPaid": False}}},
        }
        path = root / "policy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_gating_invoked_when_flag_enabled(self):
        _OscillatorStub.explain_called = 0
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with patch.object(policy_router, "ArousalOscillator", _OscillatorStub):
                with patch.object(policy_router, "tacti_enabled", side_effect=lambda name: name in {"master", "arousal_osc"}):
                    router = policy_router.PolicyRouter(
                        policy_path=self._policy_path(tmp),
                        budget_path=tmp / "budget.json",
                        circuit_path=tmp / "circuit.json",
                        event_log=tmp / "events.jsonl",
                        handlers={"mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                    )
                    controls = router._tacti_runtime_controls("coding", {}, {"agent_id": "main"})
        self.assertTrue(controls["enabled"])
        self.assertAlmostEqual(float(controls["multiplier"]), 0.73, places=6)
        self.assertEqual(_OscillatorStub.explain_called, 1)


if __name__ == "__main__":
    unittest.main()
