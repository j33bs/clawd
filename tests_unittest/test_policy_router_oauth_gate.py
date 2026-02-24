import importlib.util
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


class _DummyRequests:
    called = False

    class exceptions:
        class Timeout(Exception):
            pass

        class ConnectionError(Exception):
            pass

    @classmethod
    def post(cls, *_args, **_kwargs):
        cls.called = True
        raise AssertionError("network should not be called when oauth JWT endpoint is gated")


class TestPolicyRouterOauthGate(unittest.TestCase):
    def test_openai_oauth_jwt_is_gated_before_network(self):
        policy_router = _load_policy_router_module()

        events = []
        policy_router.log_event = lambda event_type, detail=None, path=None: events.append((event_type, detail))
        policy_router.requests = _DummyRequests
        _DummyRequests.called = False

        result = policy_router._call_openai_compatible(
            "https://api.openai.com/v1",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signature",
            "gpt-4o-mini",
            {"messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(result.get("ok"), False)
        self.assertEqual(result.get("reason_code"), "oauth_jwt_unsupported_endpoint")
        self.assertFalse(_DummyRequests.called)
        self.assertTrue(any(evt == "oauth_endpoint_blocked" for evt, _ in events))


if __name__ == "__main__":
    unittest.main()
