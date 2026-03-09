"""Tests for pure helpers in workspace/teamchat/orchestrator.py.

Covers:
- TeamChatOrchestrator._extract_route() — static method, pure dict mapping
- TeamChatOrchestrator.__init__() field assignments (context_window clamping)
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from workspace.teamchat.orchestrator import TeamChatOrchestrator


def _make_session(*, agents=None, repo_root=None):
    """Create a minimal session mock for orchestrator construction."""
    session = MagicMock()
    session.agents = agents or ["claude", "grok"]
    session.session_id = "test-session-001"
    session.repo_root = Path(repo_root or "/tmp")
    return session


def _make_router():
    return MagicMock()


# ---------------------------------------------------------------------------
# _extract_route (static method)
# ---------------------------------------------------------------------------


class TestExtractRoute(unittest.TestCase):
    """Tests for TeamChatOrchestrator._extract_route() — pure static method."""

    def test_returns_dict(self):
        result = TeamChatOrchestrator._extract_route({})
        self.assertIsInstance(result, dict)

    def test_none_input_returns_nones(self):
        result = TeamChatOrchestrator._extract_route(None)
        self.assertIsNone(result["provider"])
        self.assertIsNone(result["model"])
        self.assertIsNone(result["reason_code"])
        self.assertIsNone(result["attempts"])

    def test_extracts_provider(self):
        result = TeamChatOrchestrator._extract_route({"provider": "openai"})
        self.assertEqual(result["provider"], "openai")

    def test_extracts_model(self):
        result = TeamChatOrchestrator._extract_route({"model": "gpt-4o"})
        self.assertEqual(result["model"], "gpt-4o")

    def test_extracts_reason_code(self):
        result = TeamChatOrchestrator._extract_route({"reason_code": "ok"})
        self.assertEqual(result["reason_code"], "ok")

    def test_extracts_attempts(self):
        result = TeamChatOrchestrator._extract_route({"attempts": 3})
        self.assertEqual(result["attempts"], 3)

    def test_full_route_dict(self):
        route = {"provider": "anthropic", "model": "claude-3", "reason_code": "ok", "attempts": 1}
        result = TeamChatOrchestrator._extract_route(route)
        self.assertEqual(result["provider"], "anthropic")
        self.assertEqual(result["model"], "claude-3")
        self.assertEqual(result["reason_code"], "ok")
        self.assertEqual(result["attempts"], 1)

    def test_extra_keys_not_in_output(self):
        route = {"provider": "groq", "extra_field": "ignored", "model": "llama"}
        result = TeamChatOrchestrator._extract_route(route)
        self.assertNotIn("extra_field", result)

    def test_output_has_exactly_four_keys(self):
        result = TeamChatOrchestrator._extract_route({"provider": "x"})
        self.assertEqual(set(result.keys()), {"provider", "model", "reason_code", "attempts"})

    def test_does_not_mutate_input(self):
        route = {"provider": "openai", "model": "gpt-4"}
        original = dict(route)
        TeamChatOrchestrator._extract_route(route)
        self.assertEqual(route, original)


# ---------------------------------------------------------------------------
# __init__ field assignments
# ---------------------------------------------------------------------------


class TestOrchestratorInit(unittest.TestCase):
    """Tests for TeamChatOrchestrator.__init__() field assignments."""

    def test_context_window_default(self):
        orc = TeamChatOrchestrator(session=_make_session(), router=_make_router())
        self.assertEqual(orc.context_window, 12)

    def test_context_window_clamped_to_minimum_2(self):
        orc = TeamChatOrchestrator(
            session=_make_session(), router=_make_router(), context_window=0
        )
        self.assertEqual(orc.context_window, 2)

    def test_context_window_negative_clamped(self):
        orc = TeamChatOrchestrator(
            session=_make_session(), router=_make_router(), context_window=-5
        )
        self.assertEqual(orc.context_window, 2)

    def test_context_window_custom_value(self):
        orc = TeamChatOrchestrator(
            session=_make_session(), router=_make_router(), context_window=20
        )
        self.assertEqual(orc.context_window, 20)

    def test_witness_enabled_default_false(self):
        orc = TeamChatOrchestrator(session=_make_session(), router=_make_router())
        self.assertFalse(orc.witness_enabled)

    def test_witness_enabled_true(self):
        orc = TeamChatOrchestrator(
            session=_make_session(), router=_make_router(), witness_enabled=True
        )
        self.assertTrue(orc.witness_enabled)

    def test_session_stored(self):
        session = _make_session()
        orc = TeamChatOrchestrator(session=session, router=_make_router())
        self.assertIs(orc.session, session)

    def test_router_stored(self):
        router = _make_router()
        orc = TeamChatOrchestrator(session=_make_session(), router=router)
        self.assertIs(orc.router, router)

    def test_witness_ledger_path_default_from_repo_root(self):
        session = _make_session(repo_root="/tmp/myrepo")
        orc = TeamChatOrchestrator(session=session, router=_make_router())
        expected = Path("/tmp/myrepo") / "workspace" / "state_runtime" / "teamchat" / "witness_ledger.jsonl"
        self.assertEqual(orc.witness_ledger_path, expected)

    def test_witness_ledger_path_custom(self):
        orc = TeamChatOrchestrator(
            session=_make_session(),
            router=_make_router(),
            witness_ledger_path="/custom/path/ledger.jsonl",
        )
        self.assertEqual(orc.witness_ledger_path, Path("/custom/path/ledger.jsonl"))


if __name__ == "__main__":
    unittest.main()
