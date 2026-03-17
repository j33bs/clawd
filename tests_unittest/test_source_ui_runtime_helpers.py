import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

import api.portfolio as portfolio  # noqa: E402


class SourceUiRuntimeHelperTests(unittest.TestCase):
    def test_load_teamchat_sessions_ignores_stopped_rows(self):
        with tempfile.TemporaryDirectory() as td:
            teamchat_root = Path(td)
            state_root = teamchat_root / "state"
            session_root = teamchat_root / "sessions"
            state_root.mkdir(parents=True, exist_ok=True)
            session_root.mkdir(parents=True, exist_ok=True)

            (state_root / "session-stopped.json").write_text(
                json.dumps(
                    {
                        "session_id": "session-stopped",
                        "task": "Old stopped task",
                        "status": "stopped:repeated_failures",
                        "cycle": 3,
                        "accepted_reports": 0,
                    }
                ),
                encoding="utf-8",
            )
            (state_root / "session-complete.json").write_text(
                json.dumps(
                    {
                        "session_id": "session-complete",
                        "task": "Finished task",
                        "status": "completed",
                        "cycle": 4,
                        "accepted_reports": 1,
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(portfolio, "TEAMCHAT_ROOT", teamchat_root):
                payload = portfolio._load_teamchat_sessions(limit=4)

        self.assertEqual(payload["active_count"], 0)
        self.assertEqual(payload["status"], "history")
        self.assertIn("ended as", payload["summary"])

    def test_extract_phase1_item_requires_live_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            status_path = temp_root / "phase1_idle_status.json"
            lock_pid_path = temp_root / "phase1_idle_run.lock" / "pid"
            fishtank_state_path = temp_root / "fishtank_state.json"
            lock_pid_path.parent.mkdir(parents=True, exist_ok=True)

            status_path.write_text(
                json.dumps({"status": "running", "commandlet_name": "Phase One"}),
                encoding="utf-8",
            )
            lock_pid_path.write_text("999999\n", encoding="utf-8")
            fishtank_state_path.write_text(
                json.dumps({"frontend_process_running": False, "frontend_last_status": "idle"}),
                encoding="utf-8",
            )

            with (
                mock.patch.object(portfolio, "PHASE1_STATUS_PATH", status_path),
                mock.patch.object(portfolio, "PHASE1_LOCK_PID_PATH", lock_pid_path),
                mock.patch.object(portfolio, "FISHTANK_STATE_PATH", fishtank_state_path),
                mock.patch.object(portfolio.os, "kill", side_effect=OSError()),
            ):
                rows = portfolio._extract_phase1_item()

        self.assertEqual(rows, [])

    def test_runtime_agents_sort_controllable_rows_first(self):
        with tempfile.TemporaryDirectory() as td:
            ledger_path = Path(td) / "local_exec" / "jobs.jsonl"
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("", encoding="utf-8")
            with mock.patch.object(
                portfolio,
                "_latest_noncron_session",
                return_value={"updatedAt": 1773716544471, "key": "agent:main:main"},
            ):
                rows = portfolio._load_runtime_agents(
                    work_items=[
                        {
                            "id": "local_exec:123",
                            "title": "Local Exec Job",
                            "status": "running",
                            "detail": "Doing work",
                            "source": str(ledger_path),
                        }
                    ],
                    teamchat={"sessions": []},
                    components=[],
                    model_ops={"agents": [{"id": "main", "model": "minimax-portal/MiniMax-M2.5"}]},
                )

        self.assertTrue(rows)
        self.assertEqual(rows[0]["id"], "work:local_exec:123")
        self.assertEqual(rows[0]["available_actions"], ["stop"])


if __name__ == "__main__":
    unittest.main()
