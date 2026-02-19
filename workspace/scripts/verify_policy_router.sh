#!/bin/bash
set -e

python3 - <<'PY'
import json
import os
import tempfile
from pathlib import Path

ROOT = Path("workspace/scripts").resolve()
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policy_router import PolicyRouter


def write_policy(tmpdir, policy):
    path = Path(tmpdir) / "policy.json"
    path.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    return path


def base_policy():
    return {
        "version": 2,
        "defaults": {
            "allowPaid": False,
            "maxTokensPerRequest": 1024,
            "circuitBreaker": {
                "failureThreshold": 3,
                "cooldownSec": 900,
                "windowSec": 600,
                "failOn": [
                    "request_http_429",
                    "request_http_5xx",
                    "request_timeout",
                    "request_conn_error",
                ],
            },
        },
        "budgets": {
            "intents": {
                "itc_classify": {"dailyTokenBudget": 10000, "dailyCallBudget": 100, "maxCallsPerRun": 10},
                "coding": {"dailyTokenBudget": 10000, "dailyCallBudget": 100, "maxCallsPerRun": 10},
            },
            "tiers": {
                "free": {"dailyTokenBudget": 10000, "dailyCallBudget": 100},
                "paid": {"dailyTokenBudget": 10000, "dailyCallBudget": 100},
                "auth": {"dailyTokenBudget": 10000, "dailyCallBudget": 100},
            },
        },
        "providers": {},
        "routing": {"free_order": [], "intents": {}},
    }


def make_router(tmpdir, policy, handlers):
    policy_path = write_policy(tmpdir, policy)
    budget_path = Path(tmpdir) / "budget.json"
    circuit_path = Path(tmpdir) / "circuit.json"
    event_log = Path(tmpdir) / "events.jsonl"
    return PolicyRouter(
        policy_path=policy_path,
        budget_path=budget_path,
        circuit_path=circuit_path,
        event_log=event_log,
        handlers=handlers,
    )


def test_free_tier_selected():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["providers"] = {
            "freeA": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "free"}]},
            "paidA": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "paid"}]},
        }
        policy["routing"]["free_order"] = ["freeA"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free", "paidA"], "allowPaid": True}

        def ok_handler(payload, model_id, ctx):
            return {"ok": True, "text": "news"}

        router = make_router(tmpdir, policy, {"freeA": ok_handler, "paidA": ok_handler})
        result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
        assert result["ok"] and result["provider"] == "freeA", result


def test_coding_ladder_order_and_reason_codes():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["providers"] = {
            "freeA": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "free"}]},
            "openai_auth_brain": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "oa_brain"}]},
            "openai_auth_muscle": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "oa_muscle"}]},
            "claude_auth": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "ca"}]},
            "grok_api": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "grok"}]},
            "openai_api": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "oa2"}]},
            "claude_api": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "ca2"}]},
        }
        policy["routing"]["free_order"] = ["freeA"]
        policy["routing"]["intents"]["coding"] = {
            "order": ["free", "openai_auth_brain", "openai_auth_muscle", "claude_auth", "grok_api", "openai_api", "claude_api"],
            "allowPaid": True,
        }

        def fail429(payload, model_id, ctx):
            return {"ok": False, "reason_code": "request_http_429"}

        def ok_handler(payload, model_id, ctx):
            return {"ok": True, "text": "news"}

        router = make_router(
            tmpdir,
            policy,
            {
                "freeA": fail429,
                "openai_auth_brain": fail429,
                "openai_auth_muscle": fail429,
                "claude_auth": fail429,
                "grok_api": ok_handler,
                "openai_api": ok_handler,
                "claude_api": ok_handler,
            },
        )
        result = router.execute_with_escalation("coding", {"prompt": "x"}, validate_fn=lambda x: "news")
        assert result["ok"] and result["provider"] == "grok_api", result

        events = Path(tmpdir, "events.jsonl").read_text(encoding="utf-8").splitlines()
        escalations = [json.loads(line) for line in events if '"router_escalate"' in line]
        assert any(e.get("detail", {}).get("reason_code") == "request_http_429" for e in escalations), escalations


def test_circuit_breaker():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["defaults"]["circuitBreaker"]["failureThreshold"] = 2
        policy["defaults"]["circuitBreaker"]["cooldownSec"] = 999
        policy["providers"] = {
            "freeA": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "free"}]},
        }
        policy["routing"]["free_order"] = ["freeA"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free"]}

        def fail429(payload, model_id, ctx):
            return {"ok": False, "reason_code": "request_http_429"}

        router = make_router(tmpdir, policy, {"freeA": fail429})
        router.execute_with_escalation("itc_classify", {"prompt": "x"})
        router.execute_with_escalation("itc_classify", {"prompt": "x"})
        result = router.execute_with_escalation("itc_classify", {"prompt": "x"})
        assert not result["ok"] and result["reason_code"] == "circuit_open", result


def test_budget_enforcement_and_token_cap():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["defaults"]["maxTokensPerRequest"] = 5
        policy["providers"] = {
            "freeA": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "free"}]},
        }
        policy["routing"]["free_order"] = ["freeA"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free"]}

        def ok_handler(payload, model_id, ctx):
            return {"ok": True, "text": "news"}

        router = make_router(tmpdir, policy, {"freeA": ok_handler})

        # token cap should block
        long_text = "x" * 200
        res_cap = router.execute_with_escalation("itc_classify", {"prompt": long_text})
        assert not res_cap["ok"] and res_cap["reason_code"] == "request_token_cap_exceeded", res_cap

    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["defaults"]["maxTokensPerRequest"] = 2000
        policy["budgets"]["intents"]["itc_classify"]["dailyCallBudget"] = 1
        policy["budgets"]["tiers"]["free"]["dailyCallBudget"] = 1
        policy["providers"] = {
            "freeA": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "free"}]},
        }
        policy["routing"]["free_order"] = ["freeA"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free"]}

        def ok_handler(payload, model_id, ctx):
            return {"ok": True, "text": "news"}

        router = make_router(tmpdir, policy, {"freeA": ok_handler})

        # budget allows once, then blocks
        res_ok = router.execute_with_escalation("itc_classify", {"prompt": "short"})
        assert res_ok["ok"], res_ok
        res_block = router.execute_with_escalation("itc_classify", {"prompt": "short"})
        assert not res_block["ok"] and res_block["reason_code"] == "intent_call_budget_exhausted", res_block


def test_missing_anthropic_key_falls_back_to_local_vllm():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["providers"] = {
            "anthropic": {
                "enabled": True,
                "paid": False,
                "tier": "auth",
                "type": "anthropic",
                "apiKeyEnv": "ANTHROPIC_API_KEY",
                "models": [{"id": "claude-3-5-sonnet"}],
            },
            "local_vllm_assistant": {
                "enabled": True,
                "paid": False,
                "tier": "free",
                "type": "openai_compatible",
                "baseUrl": "http://127.0.0.1:8001/v1",
                "models": [{"id": "local-assistant"}],
            },
        }
        policy["routing"]["free_order"] = ["anthropic", "local_vllm_assistant"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free"], "allowPaid": False}

        def ok_handler(payload, model_id, ctx):
            return {"ok": True, "text": "news"}

        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            router = make_router(tmpdir, policy, {"local_vllm_assistant": ok_handler})
            result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
            assert result["ok"] and result["provider"] == "local_vllm_assistant", result

            events = Path(tmpdir, "events.jsonl").read_text(encoding="utf-8").splitlines()
            skips = [json.loads(line) for line in events if '"router_skip"' in line]
            assert any(
                e.get("detail", {}).get("provider") == "anthropic"
                and e.get("detail", {}).get("reason_code") == "missing_api_key"
                for e in skips
            ), skips
        finally:
            if old_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_key


def test_anthropic_missing_key_is_ineligible():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["providers"] = {
            "anthropic": {
                "enabled": True,
                "paid": False,
                "tier": "auth",
                "type": "anthropic",
                "apiKeyEnv": "ANTHROPIC_API_KEY",
                "models": [{"id": "claude-3-5-sonnet"}],
            },
        }
        policy["routing"]["free_order"] = ["anthropic"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free"], "allowPaid": False}

        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            router = make_router(tmpdir, policy, {})
            result = router.execute_with_escalation("itc_classify", {"prompt": "hello"})
            assert not result["ok"] and result["reason_code"] == "missing_api_key", result
        finally:
            if old_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_key


def test_local_vllm_assistant_without_api_key_env_is_eligible():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["providers"] = {
            "local_vllm_assistant": {
                "enabled": True,
                "paid": False,
                "tier": "free",
                "type": "openai_compatible",
                "baseUrl": "http://127.0.0.1:8001/v1",
                "auth": {"type": "bearer_optional"},
                "models": [{"id": "local-assistant"}],
            },
        }
        policy["routing"]["free_order"] = ["local_vllm_assistant"]
        policy["routing"]["intents"]["itc_classify"] = {"order": ["free"], "allowPaid": False}

        def ok_handler(payload, model_id, ctx):
            return {"ok": True, "text": "news"}

        router = make_router(tmpdir, policy, {"local_vllm_assistant": ok_handler})
        result = router.execute_with_escalation("itc_classify", {"prompt": "hello"}, validate_fn=lambda x: "news")
        assert result["ok"] and result["provider"] == "local_vllm_assistant", result


def main():
    test_free_tier_selected()
    test_coding_ladder_order_and_reason_codes()
    test_circuit_breaker()
    test_budget_enforcement_and_token_cap()
    test_anthropic_missing_key_is_ineligible()
    test_local_vllm_assistant_without_api_key_env_is_eligible()
    test_missing_anthropic_key_falls_back_to_local_vllm()
    print("ok")


if __name__ == "__main__":
    main()
PY
