import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
MODULE_PATH = SOURCE_UI_ROOT / "api" / "task_store.py"

if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

SPEC = importlib.util.spec_from_file_location("_source_ui_task_store", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["_source_ui_task_store"] = MOD
SPEC.loader.exec_module(MOD)


class TaskStoreTests(unittest.TestCase):
    def test_load_tasks_no_longer_seeds_stale_dashboard_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            tasks_path = Path(td) / "tasks.json"
            mission_path = Path(td) / "source_mission.json"
            archive_path = Path(td) / "archived_tasks.json"
            mission_path.write_text(json.dumps({"tasks": []}, indent=2), encoding="utf-8")
            archive_path.write_text("[]\n", encoding="utf-8")

            with (
                mock.patch.object(MOD, "TASKS_PATH", tasks_path),
                mock.patch.object(MOD, "SOURCE_MISSION_CONFIG_PATH", mission_path),
                mock.patch.object(MOD, "ARCHIVED_TASKS_PATH", archive_path),
            ):
                tasks = MOD.load_tasks(tasks_path)

        self.assertEqual(tasks, [])

    def test_archived_source_mission_tasks_do_not_reopen_without_flag(self):
        with tempfile.TemporaryDirectory() as td:
            mission_path = Path(td) / "source_mission.json"
            archive_path = Path(td) / "archived_tasks.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"id": "source-001", "title": "Universal Context Packet"},
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "sm-001",
                            "title": "Universal Context Packet",
                            "origin": "source_mission_config",
                            "status": "archived",
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD, "SOURCE_MISSION_CONFIG_PATH", mission_path),
                mock.patch.object(MOD, "ARCHIVED_TASKS_PATH", archive_path),
                mock.patch.object(MOD, "_source_mission_signals", return_value={}),
                mock.patch.object(
                    MOD,
                    "_source_mission_task_row",
                    return_value={
                        "id": "sm-001",
                        "title": "Universal Context Packet",
                        "status": "backlog",
                        "origin": "source_mission_config",
                    },
                ),
            ):
                tasks, changed = MOD._merge_source_mission_tasks([])

        self.assertFalse(changed)
        self.assertEqual(tasks, [])

    def test_archived_source_mission_tasks_can_reopen_with_flag(self):
        with tempfile.TemporaryDirectory() as td:
            mission_path = Path(td) / "source_mission.json"
            archive_path = Path(td) / "archived_tasks.json"
            mission_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"id": "source-001", "title": "Universal Context Packet", "reopen": True},
                        ]
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            archive_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "sm-001",
                            "title": "Universal Context Packet",
                            "origin": "source_mission_config",
                            "status": "archived",
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(MOD, "SOURCE_MISSION_CONFIG_PATH", mission_path),
                mock.patch.object(MOD, "ARCHIVED_TASKS_PATH", archive_path),
                mock.patch.object(MOD, "_source_mission_signals", return_value={}),
                mock.patch.object(
                    MOD,
                    "_source_mission_task_row",
                    return_value={
                        "id": "sm-001",
                        "title": "Universal Context Packet",
                        "status": "backlog",
                        "origin": "source_mission_config",
                    },
                ),
            ):
                tasks, changed = MOD._merge_source_mission_tasks([])

        self.assertTrue(changed)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], "sm-001")


if __name__ == "__main__":
    unittest.main()
