import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "source-ui" / "app.py"
SPEC = importlib.util.spec_from_file_location("_source_ui_app", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["_source_ui_app"] = MOD
SPEC.loader.exec_module(MOD)


class TestMissionTaskHydration(unittest.TestCase):
    def test_normalize_tasks_hydrates_backlog_metadata(self):
        tasks, changed = MOD.DemoDataGenerator.normalize_tasks(
            [
                {
                    "id": 101,
                    "title": "[Dali] Canonicalize mission state across UI, API, and files",
                    "description": "Keep Source mission state consistent across the backend, task board, and canonical artifacts.",
                    "status": "backlog",
                    "priority": "high",
                    "assignee": "dali",
                    "artifact_path": "workspace/source-ui/source_mission.json",
                }
            ]
        )

        self.assertTrue(changed)
        task = tasks[0]
        self.assertEqual(task["origin"], "source_mission_config")
        self.assertEqual(task["mission_task_id"], "source-101")
        self.assertEqual(task["sequence"], 1)
        self.assertIn("workspace/source-ui/source_mission.json", task["definition_of_done"])
        self.assertEqual(task["status_reason"], "Queued in Source backlog.")

    def test_auto_start_skips_source_mission_backlog_tasks(self):
        tasks, changed = MOD.DemoDataGenerator.auto_start_backlog_tasks(
            [{"id": "dali"}],
            [
                {
                    "id": 101,
                    "title": "Canonicalize mission state",
                    "status": "backlog",
                    "priority": "high",
                    "origin": "source_mission_config",
                    "assignee": "dali",
                    "created_at": "2026-03-16T00:00:00Z",
                }
            ],
        )

        self.assertFalse(changed)
        self.assertEqual(tasks[0]["status"], "backlog")

    def test_auto_start_advances_api_created_backlog_tasks(self):
        tasks, changed = MOD.DemoDataGenerator.auto_start_backlog_tasks(
            [{"id": "dali"}],
            [
                {
                    "id": 301,
                    "title": "Fresh API-created task",
                    "status": "backlog",
                    "priority": "high",
                    "origin": "source_ui_api",
                    "assignee": "dali",
                    "created_at": "2026-03-16T00:00:00Z",
                }
            ],
        )

        self.assertTrue(changed)
        self.assertEqual(tasks[0]["status"], "in_progress")
        self.assertIn("started_at", tasks[0])

    def test_normalize_preserves_api_task_origin(self):
        tasks, changed = MOD.DemoDataGenerator.normalize_tasks(
            [
                {
                    "id": 302,
                    "title": "API-created task remains API-origin",
                    "status": "backlog",
                    "priority": "medium",
                    "origin": "source_ui_api",
                    "assignee": "dali",
                    "created_at": "2026-03-16T00:00:00Z",
                }
            ]
        )

        self.assertTrue(changed)
        self.assertEqual(tasks[0]["origin"], "source_ui_api")
        self.assertEqual(tasks[0]["status_reason"], "Queued in Source backlog.")


class TestBacklogOutcomeReconciliation(unittest.TestCase):
    def test_result_outcome_moves_task_to_review_and_records_events(self):
        mission = {
            "tasks": [
                {
                    "id": 103,
                    "title": "[Dali] Instrument mission observability and task provenance",
                    "status": "in_progress",
                    "priority": "medium",
                    "assignee": "dali",
                    "mission_task_id": "source-103",
                }
            ],
            "notifications": [],
            "logs": [],
            "handoffs": [],
        }
        backlog_state = {
            "dali": {
                "task_id": "103",
                "runtime_agent": "codex",
                "outcome_kind": "result",
                "outcome_text": "wired backlog result reconciliation into Source UI",
                "outcome_at": "2026-03-16T04:00:00Z",
                "outcome_seen_ts": 1710552000,
            }
        }

        updated, changed = MOD.reconcile_backlog_state(mission, backlog_state)

        self.assertTrue(changed)
        task = updated["tasks"][0]
        self.assertEqual(task["status"], "review")
        self.assertEqual(task["progress"], 90)
        self.assertEqual(task["last_outcome_kind"], "result")
        self.assertEqual(task["last_outcome_runtime_agent"], "codex")
        self.assertEqual(len(updated["notifications"]), 1)
        self.assertEqual(updated["notifications"][0]["type"], "success")
        self.assertEqual(len(updated["logs"]), 1)
        self.assertEqual(updated["logs"][0]["level"], "info")
        self.assertEqual(len(updated["handoffs"]), 1)
        self.assertEqual(updated["handoffs"][0]["from_agent"], "dali")
        self.assertEqual(updated["handoffs"][0]["to_agent"], "source-ui")

    def test_reconcile_is_idempotent_for_same_outcome(self):
        mission = {
            "tasks": [
                {
                    "id": 104,
                    "title": "[Dali] Implement c_lawd-Dali handoff substrate",
                    "status": "in_progress",
                    "priority": "high",
                    "assignee": "dali",
                    "mission_task_id": "source-104",
                }
            ],
            "notifications": [],
            "logs": [],
            "handoffs": [],
        }
        backlog_state = {
            "dali": {
                "task_id": "104",
                "runtime_agent": "codex",
                "outcome_kind": "blocker",
                "outcome_text": "waiting on canonical handoff grammar",
                "outcome_at": "2026-03-16T05:00:00Z",
                "outcome_seen_ts": 1710555600,
            }
        }

        first, first_changed = MOD.reconcile_backlog_state(mission, backlog_state)
        second, second_changed = MOD.reconcile_backlog_state(first, backlog_state)

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(first["tasks"][0]["status"], "backlog")
        self.assertEqual(len(second["notifications"]), 1)
        self.assertEqual(len(second["logs"]), 1)
        self.assertEqual(len(second["handoffs"]), 1)


if __name__ == "__main__":
    unittest.main()
