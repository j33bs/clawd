import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_policy_router_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "policy_router.py"
    spec = importlib.util.spec_from_file_location("policy_router", str(mod_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPolicyRouterCuriosityFallback(unittest.TestCase):
    def test_response_null_adds_curiosity_payload(self):
        policy_router = _load_policy_router_module()
        policy_router.requests = type(
            "_ReachableRequests",
            (),
            {
                "get": staticmethod(lambda _url, timeout=None: type("Resp", (), {"status_code": 200})()),
                "exceptions": type(
                    "exceptions",
                    (),
                    {"Timeout": type("Timeout", (Exception,), {}), "ConnectionError": type("ConnectionError", (Exception,), {})},
                ),
            },
        )

        def _curiosity_stub(**kwargs):
            del kwargs
            return {
                "triggered": True,
                "seed": "abc123",
                "leads": [
                    "perturbed_query: test",
                    "research_queue: x",
                    "open_question: y",
                ],
            }

        policy_router._curiosity_route_on_failure = _curiosity_stub

        policy = {
            "version": 2,
            "defaults": {
                "allowPaid": False,
                "maxTokensPerRequest": 4096,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {"conversation": {"dailyTokenBudget": 999999, "dailyCallBudget": 999, "maxCallsPerRun": 10}},
                "tiers": {"free": {"dailyTokenBudget": 999999, "dailyCallBudget": 999}},
            },
            "providers": {
                "local_vllm_assistant": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "provider_id": "local_vllm",
                    "type": "openai_compatible",
                    "baseUrl": "http://127.0.0.1:8001/v1",
                    "models": [{"id": "local-assistant", "maxInputChars": 50000}],
                }
            },
            "routing": {
                "free_order": ["local_vllm_assistant"],
                "intents": {"conversation": {"order": ["local_vllm_assistant"], "allowPaid": False}},
            },
        }

        def _handler(_payload, _model_id, _runtime_context):
            return {"ok": True, "text": ""}

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = policy_router.PolicyRouter(
                policy_path=policy_path,
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={"local_vllm_assistant": _handler},
            )
            out = router.execute_with_escalation("conversation", {"prompt": "hi"}, {"input_text": "hi"})

        self.assertFalse(out.get("ok"), out)
        self.assertEqual(out.get("reason_code"), "response_null")
        self.assertIn("curiosity", out)
        self.assertTrue(out["curiosity"].get("triggered"))
        self.assertGreaterEqual(len(out["curiosity"].get("leads", [])), 3)


if __name__ == "__main__":
    unittest.main()
