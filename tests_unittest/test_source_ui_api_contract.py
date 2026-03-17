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
        handler._state.tasks = [
            {"id": "source-001", "title": "Universal Context Packet", "status": "backlog"},
            {"id": "source-002", "title": "Mission Control Timeline", "status": "review"},
        ]
        with (
            mock.patch.object(handler, "refresh_state_from_source_mission", return_value=False),
            mock.patch.object(
                MOD,
                "portfolio_payload",
                return_value={
                    "components": [{"id": "gateway", "status": "healthy"}],
                    "health_metrics": {"cpu": 12, "memory": 34, "disk": 56, "gpu": 0},
                },
            ),
            mock.patch.object(
                MOD,
                "get_status_data",
                return_value={"memory": {"process_rss_mb": 12.5}, "cron": {"status": "ok"}},
            ),
        ):
            handler.handle_api(MOD.urlparse("/api/status"))

        payload = handler.send_json.call_args.args[0]
        self.assertIn("agents", payload)
        self.assertIn("truth", payload)
        self.assertEqual(payload["memory"]["process_rss_mb"], 12.5)
        self.assertEqual(payload["cron"]["status"], "ok")
        self.assertEqual(payload["components"][0]["id"], "gateway")
        self.assertEqual(payload["health_metrics"]["cpu"], 12)
        self.assertEqual(payload["tasks_total"], 2)
        self.assertEqual(payload["task_counts"]["backlog"], 1)
        self.assertEqual(payload["task_counts"]["review"], 1)

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
