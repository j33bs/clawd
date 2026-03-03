import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from memory.arousal_tracker import load_state as load_arousal_state  # noqa: E402
from memory.relationship_tracker import load_state as load_relationship_state  # noqa: E402
from teamchat.orchestrator import TeamChatOrchestrator  # noqa: E402
from teamchat.session import TeamChatSession  # noqa: E402


class _Router:
    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        del payload, context_metadata, validate_fn
        agent = str(intent).split(":", 1)[1] if ":" in str(intent) else "unknown"
        return {
            "ok": True,
            "provider": "mock_provider",
            "model": "mock_model",
            "reason_code": "success",
            "attempts": 1,
            "text": f"{agent} response",
        }


class TestMemoryMessageHooks(unittest.TestCase):
    def test_trackers_update_deterministically_without_raw_content(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            session = TeamChatSession(session_id="memory-hook", agents=["planner"], repo_root=repo_root)
            session.append_user("hello there")
            session.append_agent(agent="planner", content="done", route={"provider": "mock"})

            arousal = load_arousal_state(repo_root=repo_root)
            rel = load_relationship_state(repo_root=repo_root)

            a_row = arousal["sessions"]["memory-hook"]
            r_row = rel["sessions"]["memory-hook"]
            self.assertEqual(1, a_row["user_events"])
            self.assertEqual(1, a_row["assistant_events"])
            self.assertEqual(1, r_row["user_events"])
            self.assertEqual(1, r_row["assistant_events"])
            self.assertEqual(64, len(a_row["last_content_hash"]))
            self.assertEqual(64, len(r_row["last_content_hash"]))
            self.assertNotIn("hello there", json.dumps(arousal))
            self.assertNotIn("hello there", json.dumps(rel))

    def test_handler_path_invokes_tracker_once_per_append(self):
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td)
            session = TeamChatSession(session_id="once-hooks", agents=["planner"], repo_root=repo_root)
            orchestrator = TeamChatOrchestrator(session=session, router=_Router(), witness_enabled=False)
            with patch("teamchat.session.process_message_event") as mocked:
                result = orchestrator.run_cycle(user_message="ship this", max_turns=1)
            self.assertTrue(result["ok"])
            # user append + one agent append
            self.assertEqual(2, mocked.call_count)
            event = mocked.call_args_list[0].args[0]
            self.assertIn("content_hash", event)
            self.assertNotIn("content", event)


if __name__ == "__main__":
    unittest.main()
