import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

import teamchat.orchestrator as orchestrator_mod  # noqa: E402
from teamchat.orchestrator import TeamChatOrchestrator  # noqa: E402
from teamchat.session import TeamChatSession  # noqa: E402


class _FakeRouter:
    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        agent = str(intent).split(":", 1)[1] if ":" in str(intent) else "unknown"
        return {
            "ok": True,
            "provider": "mock_provider",
            "model": "mock_model",
            "reason_code": "success",
            "attempts": 1,
            "text": f"{agent} reply",
        }


class TestTeamChatWitness(unittest.TestCase):
    def test_witness_commit_called_for_each_agent_turn(self):
        with tempfile.TemporaryDirectory() as td:
            records = []

            def _capture_commit(*, record, ledger_path):
                records.append({"record": dict(record), "ledger_path": str(ledger_path)})
                return {"hash": f"h{len(records)}", "seq": len(records), "prev_hash": None, "timestamp_utc": "2026-02-20T00:00:00Z"}

            session = TeamChatSession(
                session_id="session_witness",
                agents=["planner", "coder"],
                repo_root=Path(td),
            )
            orchestrator = TeamChatOrchestrator(
                session=session,
                router=_FakeRouter(),
                witness_enabled=True,
                witness_ledger_path=Path(td) / "workspace" / "audit" / "witness_ledger.jsonl",
            )
            with patch.object(orchestrator_mod, "witness_commit", side_effect=_capture_commit):
                result = orchestrator.run_cycle(user_message="Need a plan", max_turns=2)

        self.assertTrue(result["ok"])
        self.assertEqual(len(records), 2)
        self.assertEqual([row["record"]["agent"] for row in records], ["planner", "coder"])
        self.assertEqual([row["record"]["turn"] for row in records], [1, 2])
        self.assertTrue(all(row["record"]["event"] == "teamchat_turn" for row in records))


if __name__ == "__main__":
    unittest.main()
