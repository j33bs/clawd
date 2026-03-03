import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from teamchat.orchestrator import TeamChatOrchestrator  # noqa: E402
from teamchat.session import TeamChatSession  # noqa: E402


class _FakeRouter:
    def __init__(self):
        self.calls = []

    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        self.calls.append(
            {
                "intent": intent,
                "payload": dict(payload or {}),
                "context": dict(context_metadata or {}),
            }
        )
        agent = str(intent).split(":", 1)[1] if ":" in str(intent) else "unknown"
        return {
            "ok": True,
            "provider": "mock_provider",
            "model": "mock_model",
            "reason_code": "success",
            "attempts": 1,
            "text": f"{agent} reply",
        }


class TestTeamChatBasic(unittest.TestCase):
    def test_session_appends_jsonl_round_robin_and_runtime_only(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            router = _FakeRouter()
            session = TeamChatSession(
                session_id="session_basic",
                agents=["planner", "coder", "critic"],
                repo_root=repo_root,
            )
            orchestrator = TeamChatOrchestrator(session=session, router=router, witness_enabled=False)
            result = orchestrator.run_cycle(user_message="Ship the fix", max_turns=3)

            self.assertTrue(result["ok"])
            self.assertEqual(result["turns"], 3)
            self.assertEqual(
                [call["intent"] for call in router.calls],
                ["teamchat:planner", "teamchat:coder", "teamchat:critic"],
            )

            rows = session.messages()
            self.assertEqual([row["role"] for row in rows], ["user", "agent:planner", "agent:coder", "agent:critic"])
            self.assertEqual(rows[0]["content"], "Ship the fix")
            self.assertEqual(session.store.path, repo_root / "workspace" / "state_runtime" / "teamchat" / "sessions" / "session_basic.jsonl")

            created_files = [p for p in (repo_root / "workspace").rglob("*") if p.is_file()]
            self.assertTrue(created_files)
            for path in created_files:
                normalized = str(path).replace("\\", "/")
                self.assertIn("/workspace/state_runtime/", normalized)


if __name__ == "__main__":
    unittest.main()
