import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
MODULE_PATH = SOURCE_UI_ROOT / "app.py"

if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

SPEC = importlib.util.spec_from_file_location("_source_ui_app_contract", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["_source_ui_app_contract"] = MOD
SPEC.loader.exec_module(MOD)


class SourceUIApiContractTests(unittest.TestCase):
    def _make_handler(self):
        handler = object.__new__(MOD.SourceUIHandler)
        handler._config = MOD.Config(static_dir=str(SOURCE_UI_ROOT / "static"))
        handler._state = MOD.State()
        handler.send_json = mock.Mock()
        return handler

    def test_load_source_mission_accepts_plain_config_payload(self):
        with tempfile.TemporaryDirectory() as td:
            mission_path = Path(td) / "source_mission.json"
            runtime_path = Path(td) / "source_runtime_state.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "statement": "Build a better Source UI.",
                        "tasks": [{"id": "source-001", "title": "Universal Context Packet"}],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD, "SOURCE_MISSION_PATH", mission_path),
                mock.patch.object(MOD, "SOURCE_RUNTIME_STATE_PATH", runtime_path),
            ):
                mission = MOD.DemoDataGenerator.load_source_mission()

        self.assertIsInstance(mission, dict)
        self.assertEqual(mission["statement"], "Build a better Source UI.")
        self.assertEqual(mission["tasks"][0]["id"], "source-001")

    def test_hydrate_task_metadata_does_not_double_prefix_source_ids(self):
        task, changed = MOD.DemoDataGenerator.hydrate_task_metadata(
            {"id": "source-001", "title": "Universal Context Packet"},
            index=0,
        )

        self.assertTrue(changed)
        self.assertEqual(task["mission_task_id"], "source-001")

    def test_status_endpoint_merges_tacti_status_data(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "portfolio_payload",
                return_value={
                    "runtime_agents": [{"id": "session:main", "name": "c_lawd", "status": "working"}],
                    "scheduled_jobs": [{"id": "cron-1", "name": "Hourly Check", "cron": "0 * * * *"}],
                    "activity_logs": [{"level": "info", "message": "live log"}],
                    "components": [{"id": "gateway", "status": "healthy"}],
                    "health_metrics": {"cpu": 12, "memory": 34, "disk": 56, "gpu": 0},
                    "gateway_connected": True,
                },
            ),
            mock.patch.object(
                MOD,
                "get_status_data",
                return_value={"memory": {"process_rss_mb": 12.5}, "cron": {"status": "ok"}},
            ),
            mock.patch.object(
                MOD,
                "load_task_store_tasks",
                return_value=[
                    {"id": 1001, "title": "Live task", "status": "backlog", "origin": "dashboard"},
                    {"id": 1002, "title": "Review task", "status": "review", "origin": "dashboard"},
                    {"id": "sm-001", "title": "Mission task", "status": "backlog", "origin": "source_mission_config"},
                ],
            ),
        ):
            handler.handle_api(MOD.urlparse("/api/status"))

        payload = handler.send_json.call_args.args[0]
        self.assertIn("agents", payload)
        self.assertIn("truth", payload)
        self.assertEqual(payload["memory"]["process_rss_mb"], 12.5)
        self.assertEqual(payload["cron"]["status"], "ok")
        self.assertEqual(payload["agents"][0]["id"], "session:main")
        self.assertEqual(payload["scheduled_jobs"][0]["id"], "cron-1")
        self.assertEqual(payload["logs"][0]["message"], "live log")
        self.assertEqual(payload["components"][0]["id"], "gateway")
        self.assertEqual(payload["health_metrics"]["cpu"], 12)
        self.assertTrue(payload["gateway_connected"])
        self.assertEqual(payload["tasks_total"], 2)
        self.assertEqual(payload["task_counts"]["backlog"], 1)
        self.assertEqual(payload["task_counts"]["review"], 1)
        self.assertEqual(len(payload["tasks"]), 2)
        self.assertTrue(all(str(task.get("origin")) != "source_mission_config" for task in payload["tasks"]))

    def test_tasks_endpoint_uses_canonical_task_store(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "load_task_store_tasks",
                return_value=[
                    {"id": 1001, "title": "Live task", "status": "backlog", "origin": "dashboard"},
                    {"id": "sm-001", "title": "Mission task", "status": "backlog", "origin": "source_mission_config"},
                ],
            ),
        ):
            handler.handle_api(MOD.urlparse("/api/tasks"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], 1001)

    def test_agents_endpoint_uses_runtime_agents(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "portfolio_payload", return_value={"runtime_agents": [{"id": "session:main", "name": "c_lawd"}]}),
        ):
            handler.handle_api(MOD.urlparse("/api/agents"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload[0]["id"], "session:main")

    def test_schedule_endpoint_uses_runtime_schedules(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "portfolio_payload", return_value={"scheduled_jobs": [{"id": "cron-1", "name": "Hourly"}]}),
        ):
            handler.handle_api(MOD.urlparse("/api/schedule"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload[0]["id"], "cron-1")

    def test_logs_endpoint_uses_runtime_activity_logs(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "portfolio_payload", return_value={"activity_logs": [{"level": "info", "message": "live log"}]}),
        ):
            handler.handle_api(MOD.urlparse("/api/logs"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload[0]["message"], "live log")

    def test_create_schedule_endpoint_calls_runtime_creator(self):
        handler = self._make_handler()
        handler._read_json_body = mock.Mock(return_value={"name": "Nightly"})

        with mock.patch.object(MOD, "_create_schedule_job", return_value={"success": True, "id": "cron-1"}) as creator:
            handler.create_schedule()

        creator.assert_called_once_with({"name": "Nightly"})
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["id"], "cron-1")

    def test_control_agent_endpoint_calls_runtime_action(self):
        handler = self._make_handler()

        with mock.patch.object(MOD, "_control_runtime_agent_action", return_value={"success": True, "summary": "Stopped"}) as control:
            handler.control_agent("service:dali-fishtank.service", "stop")

        control.assert_called_once_with("service:dali-fishtank.service", "stop")
        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["summary"], "Stopped")

    def test_persist_source_mission_writes_runtime_state_not_config(self):
        with tempfile.TemporaryDirectory() as td:
            mission_path = Path(td) / "source_mission.json"
            runtime_path = Path(td) / "source_runtime_state.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "statement": "Build a better Source UI.",
                        "tasks": [
                            {
                                "id": "source-001",
                                "title": "Universal Context Packet",
                                "definition_of_done": "Keep all surfaces aligned.",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            handler = self._make_handler()
            handler._state.tasks = [
                {
                    "id": "source-001",
                    "title": "Universal Context Packet",
                    "definition_of_done": "Keep all surfaces aligned.",
                    "status": "in_progress",
                    "progress": 65,
                    "origin": "source_mission_config",
                    "mission_task_id": "source-001",
                    "status_reason": "Active lane work in progress.",
                }
            ]
            handler._state.notifications = [{"id": 1, "title": "Task started"}]
            handler._state.handoffs = []
            handler._state.logs = [{"level": "info", "message": "Task started"}]

            with (
                mock.patch.object(MOD, "SOURCE_MISSION_PATH", mission_path),
                mock.patch.object(MOD, "SOURCE_RUNTIME_STATE_PATH", runtime_path),
            ):
                handler.persist_source_mission()
                merged = MOD.DemoDataGenerator.load_source_mission()

            config_payload = json.loads(mission_path.read_text(encoding="utf-8"))
            runtime_payload = json.loads(runtime_path.read_text(encoding="utf-8"))

            self.assertNotIn("updated_at", config_payload)
            self.assertNotIn("notifications", config_payload)
            self.assertNotIn("origin", config_payload["tasks"][0])
            self.assertEqual(runtime_payload["task_overrides"][0]["status"], "in_progress")
            self.assertEqual(runtime_payload["notifications"][0]["title"], "Task started")
            self.assertEqual(merged["tasks"][0]["progress"], 65)
            self.assertEqual(merged["notifications"][0]["title"], "Task started")

    def test_tacti_dream_endpoint_returns_live_payload(self):
        handler = self._make_handler()
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(MOD, "get_dream_status", return_value={"status": "ready", "report_count": 3}),
        ):
            handler.handle_api(MOD.urlparse("/api/tacti/dream"))

        payload = handler.send_json.call_args.args[0]
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["report_count"], 3)

    def test_ain_status_payload_uses_phi_proxy(self):
        handler = self._make_handler()
        with mock.patch.object(handler, "_ain_phi_payload", return_value={"phi": 0.9405, "proxy_method": "embedding_coherence"}):
            payload = handler._ain_status_payload()

        self.assertTrue(payload["running"])
        self.assertEqual(payload["state"], "online")
        self.assertAlmostEqual(payload["total_drive"], 0.9405)


if __name__ == "__main__":
    unittest.main()
