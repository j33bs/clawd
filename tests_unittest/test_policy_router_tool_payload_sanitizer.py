import importlib.util
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _load_policy_router_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "policy_router.py"
    spec = importlib.util.spec_from_file_location("policy_router", str(mod_path))
    assert spec and spec.loader, f"Failed to load module spec for {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_sanitizer_module():
    repo_root = Path(__file__).resolve().parents[1]
    mod_path = repo_root / "workspace" / "scripts" / "tool_payload_sanitizer.py"
    spec = importlib.util.spec_from_file_location("tool_payload_sanitizer", str(mod_path))
    assert spec and spec.loader, f"Failed to load module spec for {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


class TestPolicyRouterToolPayloadSanitizer(unittest.TestCase):
    def test_case_a_tool_choice_removed_when_tools_missing(self):
        sanitizer = _load_sanitizer_module()
        payload = {"messages": [{"role": "user", "content": "hi"}], "tool_choice": "auto"}
        out = sanitizer.sanitize_tool_payload(payload, {"tool_calls_supported": True})
        self.assertNotIn("tool_choice", out)
        self.assertNotIn("tools", out)

    def test_case_b_empty_tools_remove_both(self):
        sanitizer = _load_sanitizer_module()
        payload = {"messages": [{"role": "user", "content": "hi"}], "tools": [], "tool_choice": "auto"}
        out = sanitizer.sanitize_tool_payload(payload, {"tool_calls_supported": True})
        self.assertNotIn("tools", out)
        self.assertNotIn("tool_choice", out)

    def test_case_c_caps_false_remove_both_even_if_tools_present(self):
        sanitizer = _load_sanitizer_module()
        payload = {
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {"name": "sum"}}],
            "tool_choice": "auto",
        }
        out = sanitizer.sanitize_tool_payload(payload, {"tool_calls_supported": False})
        self.assertNotIn("tools", out)
        self.assertNotIn("tool_choice", out)

    def test_capability_missing_or_unknown_fails_closed(self):
        sanitizer = _load_sanitizer_module()
        provider = {"models": [{"id": "model-a"}]}  # no tool_support/toolSupport
        caps = sanitizer.resolve_tool_call_capability(provider, "model-a")
        self.assertEqual(caps.get("tool_calls_supported"), False)

    def test_case_d_openai_dispatch_sanitizes_before_network(self):
        policy_router = _load_policy_router_module()
        seen = {}

        def _fake_post(url, json=None, headers=None, timeout=None):
            seen["url"] = url
            seen["json"] = json
            seen["headers"] = headers
            seen["timeout"] = timeout
            return _FakeResponse(200)

        provider = {"models": [{"id": "model-a"}]}  # unknown capability => fail closed
        caps = policy_router.resolve_tool_call_capability(provider, "model-a")
        payload = {
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {"name": "sum"}}],
            "tool_choice": "auto",
        }

        requests_mod = policy_router.requests if policy_router.requests is not None else SimpleNamespace()
        with patch.object(policy_router, "requests", requests_mod), patch.object(
            requests_mod, "post", side_effect=_fake_post, create=True
        ):
            out = policy_router._call_openai_compatible(
                "https://example.test/v1",
                None,
                "model-a",
                payload,
                provider_caps=caps,
            )

        self.assertTrue(out.get("ok"))
        self.assertIn("json", seen)
        self.assertNotIn("tools", seen["json"])
        self.assertNotIn("tool_choice", seen["json"])

    def test_strict_mode_raises_structured_bypass_error(self):
        sanitizer = _load_sanitizer_module()
        payload = {"messages": [{"role": "user", "content": "hi"}], "tool_choice": "auto"}
        prev = os.environ.get("OPENCLAW_STRICT_TOOL_PAYLOAD")
        os.environ["OPENCLAW_STRICT_TOOL_PAYLOAD"] = "1"
        try:
            with self.assertRaises(sanitizer.ToolPayloadBypassError) as ctx:
                sanitizer.enforce_tool_payload_invariant(
                    payload,
                    {"tool_calls_supported": True},
                    provider_id="openai_compatible",
                    model_id="model-a",
                    callsite_tag="policy_router.final_dispatch",
                )
            err = ctx.exception
            self.assertEqual(err.code, "TOOL_PAYLOAD_SANITIZER_BYPASSED")
            self.assertEqual(err.provider_id, "openai_compatible")
            self.assertEqual(err.model_id, "model-a")
            self.assertEqual(err.callsite_tag, "policy_router.final_dispatch")
        finally:
            if prev is None:
                del os.environ["OPENCLAW_STRICT_TOOL_PAYLOAD"]
            else:
                os.environ["OPENCLAW_STRICT_TOOL_PAYLOAD"] = prev


if __name__ == "__main__":
    unittest.main()
