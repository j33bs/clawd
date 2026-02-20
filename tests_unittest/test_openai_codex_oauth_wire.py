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


class _FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class TestOpenAICodexOAuthWire(unittest.TestCase):
    def test_resolve_codex_oauth_prefers_codex_auth(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            codex_path = tmp / "codex_auth.json"
            agent_path = tmp / "agent_auth.json"
            codex_path.write_text(
                json.dumps({"tokens": {"access_token": "codex-token", "account_id": "acct-1"}}),
                encoding="utf-8",
            )
            agent_path.write_text(
                json.dumps({"openai-codex": {"access": "agent-token", "type": "oauth"}}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "OPENCLAW_CODEX_AUTH_FILE": str(codex_path),
                    "OPENCLAW_AGENT_AUTH_FILE": str(agent_path),
                },
                clear=False,
            ):
                ctx = policy_router._resolve_codex_oauth_context({"wire": "codex_cli_compat"})

        self.assertEqual(ctx["api_key"], "codex-token")
        self.assertEqual(ctx["account_id"], "acct-1")
        self.assertEqual(ctx["token_source"], "codex_auth")

    def test_resolve_codex_oauth_falls_back_to_agent_auth(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            codex_path = tmp / "missing_codex_auth.json"
            agent_path = tmp / "agent_auth.json"
            agent_path.write_text(
                json.dumps({"openai-codex": {"access": "agent-token", "type": "oauth"}}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "OPENCLAW_CODEX_AUTH_FILE": str(codex_path),
                    "OPENCLAW_AGENT_AUTH_FILE": str(agent_path),
                },
                clear=False,
            ):
                ctx = policy_router._resolve_codex_oauth_context({"wire": "codex_cli_compat"})

        self.assertEqual(ctx["api_key"], "agent-token")
        self.assertEqual(ctx["token_source"], "openclaw_auth")

    def test_codex_wire_builds_expected_request(self):
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            return _FakeResponse(200, {"output_text": "ok-from-codex"})

        result = policy_router._call_codex_cli_compat(
            "https://chatgpt.com",
            "/backend-api/codex/responses",
            {"api_key": "oauth-token", "account_id": "acct-42"},
            "gpt-5.3-codex",
            {"messages": [{"role": "user", "content": "hello"}]},
            timeout=9,
            http_post=fake_post,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "ok-from-codex")
        self.assertEqual(captured["url"], "https://chatgpt.com/backend-api/codex/responses")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer oauth-token")
        self.assertEqual(captured["headers"]["ChatGPT-Account-Id"], "acct-42")
        self.assertEqual(captured["json"]["model"], "gpt-5.3-codex")
        self.assertTrue(captured["json"]["stream"])
        self.assertEqual(captured["json"]["input"][0]["role"], "user")
        self.assertEqual(captured["json"]["input"][0]["content"][0]["text"], "hello")
        self.assertIn("instructions", captured["json"])
        self.assertEqual(captured["json"]["tool_choice"], "auto")

    def test_codex_wire_error_mapping(self):
        forbidden = policy_router._call_codex_cli_compat(
            "https://chatgpt.com",
            "/backend-api/codex/responses",
            {"api_key": "oauth-token", "account_id": "acct-42"},
            "gpt-5.3-codex",
            {"messages": [{"role": "user", "content": "hello"}]},
            http_post=lambda *args, **kwargs: _FakeResponse(403, {"error": {"message": "forbidden"}}),
        )
        self.assertFalse(forbidden["ok"])
        self.assertEqual(forbidden["reason_code"], "auth_forbidden")
        self.assertEqual(forbidden["diagnostic"]["status_code"], 403)

        server_error = policy_router._call_codex_cli_compat(
            "https://chatgpt.com",
            "/backend-api/codex/responses",
            {"api_key": "oauth-token", "account_id": "acct-42"},
            "gpt-5.3-codex",
            {"messages": [{"role": "user", "content": "hello"}]},
            http_post=lambda *args, **kwargs: _FakeResponse(500, {"error": {"message": "boom"}}),
        )
        self.assertFalse(server_error["ok"])
        self.assertEqual(server_error["reason_code"], "request_http_5xx")
        self.assertEqual(server_error["diagnostic"]["status_code"], 500)

    def test_router_uses_codex_wire_mode(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            policy = {
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
                        "conversation": {
                            "dailyTokenBudget": 10000,
                            "dailyCallBudget": 100,
                            "maxCallsPerRun": 10,
                        }
                    },
                    "tiers": {"free": {"dailyTokenBudget": 10000, "dailyCallBudget": 100}},
                },
                "providers": {
                    "codex_provider": {
                        "enabled": True,
                        "paid": False,
                        "tier": "free",
                        "type": "openai_compatible",
                        "baseUrl": "https://chatgpt.com",
                        "endpoint": "/backend-api/codex/responses",
                        "wire": "codex_cli_compat",
                        "auth": {"type": "oauth_codex"},
                        "models": [{"id": "gpt-5.3-codex", "maxInputChars": 8000}],
                    }
                },
                "routing": {
                    "free_order": ["codex_provider"],
                    "intents": {"conversation": {"order": ["free"], "allowPaid": False}},
                },
            }
            policy_path = tmp / "policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            codex_auth_path = tmp / "codex_auth.json"
            codex_auth_path.write_text(
                json.dumps({"tokens": {"access_token": "oauth-token", "account_id": "acct-42"}}),
                encoding="utf-8",
            )
            calls = {}

            def fake_post(url, json=None, headers=None, timeout=None):
                calls["url"] = url
                calls["json"] = json
                calls["headers"] = headers
                return _FakeResponse(200, {"output_text": "router-ok"})

            with patch.dict(
                os.environ,
                {
                    "OPENCLAW_CODEX_AUTH_FILE": str(codex_auth_path),
                    "OPENCLAW_AGENT_AUTH_FILE": str(tmp / "missing_agent_auth.json"),
                },
                clear=False,
            ):
                router = policy_router.PolicyRouter(
                    policy_path=policy_path,
                    budget_path=tmp / "budget.json",
                    circuit_path=tmp / "circuit.json",
                    event_log=tmp / "events.jsonl",
                    http_post=fake_post,
                )
                out = router.execute_with_escalation(
                    "conversation",
                    {"messages": [{"role": "user", "content": "hello"}]},
                )

        self.assertTrue(out["ok"])
        self.assertEqual(out["provider"], "codex_provider")
        self.assertEqual(calls["url"], "https://chatgpt.com/backend-api/codex/responses")
        self.assertEqual(calls["json"]["model"], "gpt-5.3-codex")


if __name__ == "__main__":
    unittest.main()
