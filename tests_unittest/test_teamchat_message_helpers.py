"""Tests for pure helpers in workspace/teamchat/message.py.

All stdlib — no network, no LLM calls, no file I/O.

Covers:
- utc_now
- agent_role
- make_message
- _route_minimal
- canonical_message_payload
- canonical_message_hash_v2
- legacy_message_hash
- canonical_message_hash
"""
import importlib.util as _ilu
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAMCHAT_DIR = REPO_ROOT / "workspace" / "teamchat"

_spec = _ilu.spec_from_file_location(
    "teamchat_message_real",
    str(TEAMCHAT_DIR / "message.py"),
)
msg = _ilu.module_from_spec(_spec)
sys.modules["teamchat_message_real"] = msg
_spec.loader.exec_module(msg)


# ---------------------------------------------------------------------------
# utc_now
# ---------------------------------------------------------------------------

class TestUtcNow(unittest.TestCase):
    """Tests for utc_now() — UTC ISO timestamp string."""

    def test_returns_string(self):
        self.assertIsInstance(msg.utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(msg.utc_now().endswith("Z"))

    def test_parseable(self):
        result = msg.utc_now()
        datetime.fromisoformat(result.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# agent_role
# ---------------------------------------------------------------------------

class TestAgentRole(unittest.TestCase):
    """Tests for agent_role() — prefixes name with agent: ."""

    def test_basic(self):
        self.assertEqual(msg.agent_role("claude"), "agent:claude")

    def test_strips_whitespace(self):
        self.assertEqual(msg.agent_role("  lumen  "), "agent:lumen")

    def test_returns_string(self):
        self.assertIsInstance(msg.agent_role("x"), str)

    def test_empty_name(self):
        self.assertEqual(msg.agent_role(""), "agent:")


# ---------------------------------------------------------------------------
# make_message
# ---------------------------------------------------------------------------

class TestMakeMessage(unittest.TestCase):
    """Tests for make_message() — dict builder."""

    def test_required_fields_present(self):
        m = msg.make_message(role="user", content="hello")
        self.assertIn("role", m)
        self.assertIn("content", m)
        self.assertIn("ts", m)

    def test_role_and_content_set(self):
        m = msg.make_message(role="agent:claude", content="hi")
        self.assertEqual(m["role"], "agent:claude")
        self.assertEqual(m["content"], "hi")

    def test_custom_ts(self):
        ts = "2026-03-07T12:00:00Z"
        m = msg.make_message(role="user", content="x", ts=ts)
        self.assertEqual(m["ts"], ts)

    def test_route_included_when_provided(self):
        m = msg.make_message(role="user", content="x", route={"provider": "openai"})
        self.assertIn("route", m)
        self.assertEqual(m["route"]["provider"], "openai")

    def test_route_excluded_when_none(self):
        m = msg.make_message(role="user", content="x")
        self.assertNotIn("route", m)

    def test_meta_included_when_provided(self):
        m = msg.make_message(role="user", content="x", meta={"turn": 1})
        self.assertIn("meta", m)
        self.assertEqual(m["meta"]["turn"], 1)

    def test_meta_excluded_when_none(self):
        m = msg.make_message(role="user", content="x")
        self.assertNotIn("meta", m)

    def test_returns_dict(self):
        m = msg.make_message(role="user", content="hello")
        self.assertIsInstance(m, dict)


# ---------------------------------------------------------------------------
# _route_minimal
# ---------------------------------------------------------------------------

class TestRouteMinimal(unittest.TestCase):
    """Tests for _route_minimal() — strips route to minimal fields."""

    def test_none_route_returns_empty(self):
        result = msg._route_minimal(None)
        self.assertEqual(result, {})

    def test_extra_keys_excluded(self):
        result = msg._route_minimal({"provider": "openai", "extra": "junk"})
        self.assertNotIn("extra", result)
        self.assertIn("provider", result)

    def test_none_values_excluded(self):
        result = msg._route_minimal({"provider": "openai", "model": None})
        self.assertNotIn("model", result)

    def test_known_fields_included(self):
        route = {"provider": "p", "model": "m", "reason_code": "rc", "attempts": 2}
        result = msg._route_minimal(route)
        self.assertEqual(result["provider"], "p")
        self.assertEqual(result["model"], "m")
        self.assertEqual(result["reason_code"], "rc")
        self.assertEqual(result["attempts"], 2)

    def test_returns_dict(self):
        self.assertIsInstance(msg._route_minimal({}), dict)


# ---------------------------------------------------------------------------
# canonical_message_payload
# ---------------------------------------------------------------------------

class TestCanonicalMessagePayload(unittest.TestCase):
    """Tests for canonical_message_payload() — normalized payload dict."""

    def _msg(self, **kw):
        defaults = {"ts": "2026-03-07T12:00:00Z", "role": "user", "content": "hello"}
        defaults.update(kw)
        return defaults

    def test_has_required_keys(self):
        p = msg.canonical_message_payload(self._msg())
        for key in ("session_id", "turn", "role", "content", "route_minimal", "ts"):
            self.assertIn(key, p)

    def test_role_preserved(self):
        p = msg.canonical_message_payload(self._msg(role="agent:claude"))
        self.assertEqual(p["role"], "agent:claude")

    def test_session_id_from_arg(self):
        p = msg.canonical_message_payload(self._msg(), session_id="sess-1")
        self.assertEqual(p["session_id"], "sess-1")

    def test_turn_from_arg(self):
        p = msg.canonical_message_payload(self._msg(), turn=5)
        self.assertEqual(p["turn"], 5)

    def test_turn_defaults_zero(self):
        p = msg.canonical_message_payload(self._msg())
        self.assertEqual(p["turn"], 0)

    def test_none_message_safe(self):
        # Should not raise with empty/None-like input
        p = msg.canonical_message_payload({})
        self.assertIsInstance(p, dict)


# ---------------------------------------------------------------------------
# canonical_message_hash_v2
# ---------------------------------------------------------------------------

class TestCanonicalMessageHashV2(unittest.TestCase):
    """Tests for canonical_message_hash_v2() — SHA-256 of canonical payload."""

    def _msg(self):
        return {"ts": "2026-03-07T12:00:00Z", "role": "user", "content": "hello"}

    def test_returns_string(self):
        self.assertIsInstance(msg.canonical_message_hash_v2(self._msg()), str)

    def test_hex_string(self):
        result = msg.canonical_message_hash_v2(self._msg())
        int(result, 16)  # must not raise

    def test_64_chars(self):
        result = msg.canonical_message_hash_v2(self._msg())
        self.assertEqual(len(result), 64)

    def test_deterministic(self):
        m = self._msg()
        self.assertEqual(
            msg.canonical_message_hash_v2(m),
            msg.canonical_message_hash_v2(m),
        )

    def test_different_content_differs(self):
        m1 = {"ts": "2026-03-07T12:00:00Z", "role": "user", "content": "hello"}
        m2 = {"ts": "2026-03-07T12:00:00Z", "role": "user", "content": "world"}
        self.assertNotEqual(
            msg.canonical_message_hash_v2(m1),
            msg.canonical_message_hash_v2(m2),
        )


# ---------------------------------------------------------------------------
# legacy_message_hash
# ---------------------------------------------------------------------------

class TestLegacyMessageHash(unittest.TestCase):
    """Tests for legacy_message_hash() — SHA-256 of ts+role+content."""

    def _msg(self):
        return {"ts": "2026-03-07T12:00:00Z", "role": "user", "content": "hello"}

    def test_returns_hex_string(self):
        result = msg.legacy_message_hash(self._msg())
        int(result, 16)

    def test_64_chars(self):
        self.assertEqual(len(msg.legacy_message_hash(self._msg())), 64)

    def test_deterministic(self):
        m = self._msg()
        self.assertEqual(msg.legacy_message_hash(m), msg.legacy_message_hash(m))

    def test_different_role_differs(self):
        m1 = {"ts": "t", "role": "user", "content": "hi"}
        m2 = {"ts": "t", "role": "agent", "content": "hi"}
        self.assertNotEqual(msg.legacy_message_hash(m1), msg.legacy_message_hash(m2))


# ---------------------------------------------------------------------------
# canonical_message_hash (alias)
# ---------------------------------------------------------------------------

class TestCanonicalMessageHash(unittest.TestCase):
    """Tests for canonical_message_hash() — backward-compat alias."""

    def test_same_as_legacy(self):
        m = {"ts": "2026-03-07T12:00:00Z", "role": "user", "content": "hello"}
        self.assertEqual(msg.canonical_message_hash(m), msg.legacy_message_hash(m))

    def test_returns_string(self):
        m = {"ts": "t", "role": "r", "content": "c"}
        self.assertIsInstance(msg.canonical_message_hash(m), str)


if __name__ == "__main__":
    unittest.main()
