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
            "openai_auth": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "oa"}]},
            "claude_auth": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "ca"}]},
            "grok_api": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "grok"}]},
            "openai_api": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "oa2"}]},
            "claude_api": {"enabled": True, "paid": True, "tier": "paid", "type": "mock", "models": [{"id": "ca2"}]},
        }
        policy["routing"]["free_order"] = ["freeA"]
        policy["routing"]["intents"]["coding"] = {
            "order": ["free", "openai_auth", "claude_auth", "grok_api", "openai_api", "claude_api"],
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
                "openai_auth": fail429,
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


def test_capability_routing_precedence_and_targets():
    with tempfile.TemporaryDirectory() as tmpdir:
        policy = base_policy()
        policy["providers"] = {
            "minimax_m25": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "minimax-portal/MiniMax-M2.5"}]},
            "minimax_m25_lightning": {"enabled": True, "paid": False, "tier": "free", "type": "mock", "models": [{"id": "minimax-portal/MiniMax-M2.5-Lightning"}]},
            "openai_gpt52_chat": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "gpt-5.2-chat-latest"}]},
            "openai_gpt53_codex": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "gpt-5.3-codex"}]},
            "openai_gpt53_codex_spark": {"enabled": True, "paid": False, "tier": "auth", "type": "mock", "models": [{"id": "gpt-5.3-codex-spark"}]},
            "local_vllm_assistant": {
                "enabled": True,
                "paid": False,
                "tier": "free",
                "type": "mock",
                "capabilities": {"context_window_tokens": 16384},
                "models": [{"id": "vllm/local-assistant"}],
            },
        }
        policy["routing"]["intents"]["conversation"] = {
            "order": [
                "minimax_m25",
                "minimax_m25_lightning",
                "local_vllm_assistant",
                "openai_gpt52_chat",
                "openai_gpt53_codex",
                "openai_gpt53_codex_spark",
            ],
            "allowPaid": True,
        }
        policy["routing"]["capability_router"] = {
            "enabled": True,
            "structureComplexityMinBullets": 3,
            "structureComplexityMinPaths": 2,
            "explicitTriggers": {
                "use chatgpt": "openai_gpt52_chat",
                "use codex": "openai_gpt53_codex",
            },
            "subagentProvider": "local_vllm_assistant",
            "reasoningProvider": "openai_gpt52_chat",
            "codeProvider": "openai_gpt53_codex",
            "smallCodeProvider": "openai_gpt53_codex_spark",
        }

        router = make_router(tmpdir, policy, {})

        default_sel = router.select_model("conversation", {"input_text": "hello there"})
        assert default_sel["provider"] == "minimax_m25", default_sel
        assert default_sel["model"] == "minimax-portal/MiniMax-M2.5", default_sel

        ordinary_chat_sel = router.select_model(
            "conversation",
            {"input_text": "Tell me something interesting about whales."},
        )
        assert ordinary_chat_sel["provider"] == "minimax_m25", ordinary_chat_sel
        assert ordinary_chat_sel["model"] == "minimax-portal/MiniMax-M2.5", ordinary_chat_sel
        assert ordinary_chat_sel["model"] not in {
            "gpt-5.2-chat-latest",
            "gpt-5.3-codex",
            "gpt-5.3-codex-spark",
        }, ordinary_chat_sel

        ordinary_explain = router.explain_route(
            "conversation",
            {"input_text": "Tell me something interesting about whales."},
        )
        assert ordinary_explain["matched_trigger"] == "default", ordinary_explain
        assert ordinary_explain["reason"] == "default intent routing order", ordinary_explain
        assert ordinary_explain["chosen"]["provider"] == "minimax_m25", ordinary_explain

        chatgpt_sel = router.select_model("conversation", {"input_text": "Please USE ChatGPT for this request"})
        assert chatgpt_sel["provider"] == "openai_gpt52_chat", chatgpt_sel
        assert chatgpt_sel["model"] == "gpt-5.2-chat-latest", chatgpt_sel

        codex_sel = router.select_model("conversation", {"input_text": "use codex and patch this module"})
        assert codex_sel["provider"] == "openai_gpt53_codex", codex_sel
        assert codex_sel["model"] == "gpt-5.3-codex", codex_sel

        subagent_sel = router.select_model(
            "conversation",
            {"input_text": "use chatgpt", "is_subagent": True, "agent_class": "subagent"},
        )
        assert subagent_sel["provider"] == "local_vllm_assistant", subagent_sel
        assert subagent_sel["model"] == "vllm/local-assistant", subagent_sel

        reasoning_sel = router.select_model(
            "conversation",
            {"input_text": "Plan the architecture and evaluate options with trade-offs"},
        )
        assert reasoning_sel["provider"] == "openai_gpt52_chat", reasoning_sel

        code_sel = router.select_model(
            "conversation",
            {"input_text": "Write code in Python to implement the API and add tests across two files: src/app.py tests/test_app.py"},
        )
        assert code_sel["provider"] == "openai_gpt53_codex", code_sel

        spark_sel = router.select_model(
            "conversation",
            {"input_text": "Implement a tiny patch in src/app.py", "expected_change_size": "small"},
        )
        assert spark_sel["provider"] == "openai_gpt53_codex_spark", spark_sel
        assert spark_sel["model"] == "gpt-5.3-codex-spark", spark_sel

        explain = router.explain_route("conversation", {"input_text": "please use codex now"})
        assert explain["matched_trigger"] == "explicit_phrase", explain
        assert explain["chosen"]["provider"] == "openai_gpt53_codex", explain
        assert explain["local_context_window_tokens"] == 16384, explain


def main():
    test_free_tier_selected()
    test_coding_ladder_order_and_reason_codes()
    test_circuit_breaker()
    test_budget_enforcement_and_token_cap()
    test_anthropic_missing_key_is_ineligible()
    test_local_vllm_assistant_without_api_key_env_is_eligible()
    test_missing_anthropic_key_falls_back_to_local_vllm()
    test_capability_routing_precedence_and_targets()
    print("ok")


if __name__ == "__main__":
    main()
PY
