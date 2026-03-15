import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_policy_router_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "policy_router.py"
    spec = importlib.util.spec_from_file_location("policy_router", str(mod_path))
    assert spec and spec.loader, f"Failed to load module spec for {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"choices": [{"message": {"content": "ok"}}]}

    def json(self):
        return self._payload


class _DummyRequests:
    class exceptions:
        class Timeout(Exception):
            pass

        class ConnectionError(Exception):
            pass

    last_json = None

    @classmethod
    def get(cls, _url, timeout=None):
        del timeout
        return _DummyResponse(status_code=200, payload={"data": [{"id": "local-assistant"}]})

    @classmethod
    def post(cls, _url, json=None, headers=None, timeout=None):  # noqa: A002
        del headers, timeout
        cls.last_json = dict(json or {})
        return _DummyResponse()


class TestPolicyRouterOpenAICompatibleDispatch(unittest.TestCase):
    def test_call_openai_compatible_strips_tool_fields_when_model_not_tool_capable(self):
        policy_router = _load_policy_router_module()
        policy_router.requests = _DummyRequests
        _DummyRequests.last_json = None

        payload = {
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "noop", "parameters": {"type": "object"}}}],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
        result = policy_router._call_openai_compatible(
            "http://127.0.0.1:8001/v1",
            "",
            "qwen-small",
            payload,
            provider_caps={"supports_tools": False},
        )

        self.assertTrue(result.get("ok"), result)
        self.assertTrue(result.get("tool_fields_stripped"), result)
        self.assertIsNotNone(_DummyRequests.last_json)
        self.assertNotIn("tools", _DummyRequests.last_json)
        self.assertNotIn("tool_choice", _DummyRequests.last_json)
        self.assertNotIn("parallel_tool_calls", _DummyRequests.last_json)

    def test_execute_with_escalation_openai_provider_no_longer_hits_nameerror(self):
        policy_router = _load_policy_router_module()
        policy_router.requests = _DummyRequests

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

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = policy_router.PolicyRouter(
                policy_path=policy_path,
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
            )
            out = router.execute_with_escalation("conversation", {"prompt": "hi"}, {"input_text": "hi"})

        self.assertTrue(out.get("ok"), out)
        self.assertEqual(out.get("provider"), "local_vllm_assistant")

    def test_execute_with_escalation_defers_local_vllm_during_fishtank_mode(self):
        policy_router = _load_policy_router_module()
        policy_router.requests = _DummyRequests
        policy_router.should_defer_local_vllm = lambda: True
        policy_router.enqueue_router_request = lambda **kwargs: {"id": "queue-1", "kind": "router_request", "status": "deferred"}

        calls = {"count": 0}
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
                    "type": "mock",
                    "models": [{"id": "local-assistant", "maxInputChars": 50000}],
                }
            },
            "routing": {
                "free_order": ["local_vllm_assistant"],
                "intents": {"conversation": {"order": ["local_vllm_assistant"], "allowPaid": False}},
            },
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = policy_router.PolicyRouter(
                policy_path=policy_path,
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={
                    "local_vllm_assistant": lambda payload, model_id, context: calls.update({"count": calls["count"] + 1}) or {"ok": True, "text": "ok"}
                },
            )
            out = router.execute_with_escalation("conversation", {"prompt": "hi"}, {"input_text": "hi"})

        self.assertFalse(out.get("ok"), out)
        self.assertTrue(out.get("deferred"), out)
        self.assertEqual(out.get("reason_code"), "deferred_fishtank")
        self.assertEqual(out.get("queue_entry", {}).get("id"), "queue-1")
        self.assertEqual(calls["count"], 0)

    def test_context_metadata_can_prefer_provider_and_override_model_per_request(self):
        policy_router = _load_policy_router_module()

        seen: dict[str, object] = {}

        def _handler(_payload, model_id, _context):
            seen["model_id"] = model_id
            return {"ok": True, "text": "ok"}

        policy = {
            "version": 2,
            "defaults": {
                "allowPaid": True,
                "maxTokensPerRequest": 4096,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {"conversation": {"dailyTokenBudget": 999999, "dailyCallBudget": 999, "maxCallsPerRun": 10}},
                "tiers": {"paid": {"dailyTokenBudget": 999999, "dailyCallBudget": 999}},
            },
            "providers": {
                "openai_gpt52_chat": {
                    "enabled": True,
                    "paid": True,
                    "tier": "paid",
                    "type": "mock",
                    "models": [
                        {"id": "gpt-5.2-chat-latest", "maxInputChars": 50000},
                        {"id": "gpt-5.2-chat-preview", "maxInputChars": 50000},
                    ],
                },
                "minimax_m25": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "models": [{"id": "minimax-portal/MiniMax-M2.5", "maxInputChars": 50000}],
                },
            },
            "routing": {
                "free_order": ["minimax_m25"],
                "intents": {
                    "conversation": {
                        "order": ["minimax_m25", "openai_gpt52_chat"],
                        "allowPaid": True,
                    }
                },
            },
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = policy_router.PolicyRouter(
                policy_path=policy_path,
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={"openai_gpt52_chat": _handler, "minimax_m25": lambda *_args, **_kwargs: {"ok": True, "text": "minimax"}},
            )
            out = router.execute_with_escalation(
                "conversation",
                {"prompt": "hi"},
                {
                    "input_text": "hi",
                    "preferred_provider": "openai_gpt52_chat",
                    "override_model": "gpt-5.2-chat-preview",
                },
            )

        self.assertTrue(out.get("ok"), out)
        self.assertEqual(out.get("provider"), "openai_gpt52_chat")
        self.assertEqual(out.get("model"), "gpt-5.2-chat-preview")
        self.assertEqual(seen.get("model_id"), "gpt-5.2-chat-preview")

    def test_itc_classify_can_disable_capability_router_override(self):
        policy_router = _load_policy_router_module()
        policy_router.requests = _DummyRequests

        policy = {
            "version": 2,
            "defaults": {
                "allowPaid": False,
                "maxTokensPerRequest": 4096,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {"itc_classify": {"dailyTokenBudget": 999999, "dailyCallBudget": 999, "maxCallsPerRun": 10}},
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
                },
                "claude_auth": {
                    "enabled": True,
                    "paid": False,
                    "tier": "auth",
                    "type": "anthropic_auth",
                    "readyEnv": "CLAUDE_AUTH_READY",
                },
            },
            "routing": {
                "free_order": ["local_vllm_assistant"],
                "intents": {
                    "itc_classify": {
                        "order": ["local_vllm_assistant"],
                        "allowPaid": False,
                        "allowCapabilityRouter": False,
                    }
                },
                "capability_router": {
                    "enabled": True,
                    "planningProvider": "claude_auth",
                    "reasoningProvider": "claude_auth",
                },
            },
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            router = policy_router.PolicyRouter(
                policy_path=policy_path,
                budget_path=tmp / "budget.json",
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
                handlers={"local_vllm_assistant": lambda payload, model_id, context: {"ok": True, "text": "news"}},
            )
            out = router.execute_with_escalation(
                "itc_classify",
                {"prompt": "report sources confirm partnership"},
                {"input_text": "report sources confirm partnership"},
                validate_fn=lambda text: text if text == "news" else None,
            )

        self.assertTrue(out.get("ok"), out)
        self.assertEqual(out.get("provider"), "local_vllm_assistant")

    def test_first_local_failure_reason_wins_when_no_attempts_succeed(self):
        policy_router = _load_policy_router_module()
        policy_router.requests = _DummyRequests

        policy = {
            "version": 2,
            "defaults": {
                "allowPaid": False,
                "maxTokensPerRequest": 4096,
                "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []},
            },
            "budgets": {
                "intents": {"itc_classify": {"dailyTokenBudget": 999999, "dailyCallBudget": 1, "maxCallsPerRun": 10}},
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
                },
                "groq": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "openai_compatible",
                    "baseUrl": "https://api.groq.com/openai/v1",
                    "apiKeyEnv": "GROQ_API_KEY",
                    "models": [{"id": "llama", "maxInputChars": 4000}],
                },
            },
            "routing": {
                "free_order": ["groq"],
                "intents": {
                    "itc_classify": {
                        "order": ["local_vllm_assistant", "groq"],
                        "allowPaid": False,
                        "allowCapabilityRouter": False,
                    }
                },
            },
        }

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy_path = tmp / "policy.json"
            budget_path = tmp / "budget.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            budget_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "date": policy_router._today_key(),
                        "intents": {"itc_classify": {"calls": 1, "tokens": 0}},
                        "tiers": {"free": {"calls": 0, "tokens": 0}},
                    }
                ),
                encoding="utf-8",
            )
            router = policy_router.PolicyRouter(
                policy_path=policy_path,
                budget_path=budget_path,
                circuit_path=tmp / "circuit.json",
                event_log=tmp / "events.jsonl",
            )
            out = router.execute_with_escalation(
                "itc_classify",
                {"prompt": "classify this"},
                {"input_text": "classify this"},
                validate_fn=lambda text: text,
            )

        self.assertFalse(out.get("ok"), out)
        self.assertEqual(out.get("reason_code"), "intent_call_budget_exhausted")


if __name__ == "__main__":
    unittest.main()
