import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import task_store  # noqa: E402


class TaskStoreWorldBetterTests(unittest.TestCase):
    def test_create_task_persists_world_better_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks_path = root / "tasks.json"
            archive_path = root / "archived_tasks.json"
            tasks_path.write_text("[]\n", encoding="utf-8")
            archive_path.write_text("[]\n", encoding="utf-8")
            with (
                mock.patch.object(task_store, "ARCHIVED_TASKS_PATH", archive_path),
                mock.patch.object(task_store, "SOURCE_MISSION_CONFIG_PATH", root / "missing-source-mission.json"),
                mock.patch.object(task_store, "_task_requires_review_gate", return_value=False),
            ):
                created = task_store.create_task(
                    {
                        "title": "Build packet",
                        "description": "Shared packet everywhere.",
                        "impact_vector": "continuity",
                        "time_horizon": "0-6m",
                        "beneficiaries": ["users", "operators"],
                        "public_benefit_hypothesis": "Reduce repeated explanation.",
                        "leading_indicators": ["shared packet coverage"],
                        "guardrails": ["show provenance"],
                        "evidence_status": "operational",
                        "reversibility": "high",
                        "leverage": "platform",
                    },
                    path=tasks_path,
                )
                stored = task_store.load_tasks(path=tasks_path)

        self.assertEqual(created["impact_vector"], "continuity")
        self.assertEqual(stored[0]["beneficiaries"], ["users", "operators"])
        self.assertEqual(stored[0]["guardrails"], ["show provenance"])
        self.assertEqual(stored[0]["leverage"], "platform")


if __name__ == "__main__":
    unittest.main()
