import tempfile
import unittest
from pathlib import Path

from workspace.discord_surface.store import create_task, default_tasks_doc, move_task, save_tasks, load_tasks


class TestDiscordStore(unittest.TestCase):
    def test_create_and_move_task(self):
        doc = default_tasks_doc()
        task = create_task(doc, title="Check sim", project="ops", details="details", created_by="discord")
        self.assertEqual(task["status"], "todo")
        moved = move_task(doc, task_id=task["id"], status="in_progress", moved_by="discord")
        self.assertEqual(moved["status"], "in_progress")

    def test_save_and_load_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tasks.json"
            doc = default_tasks_doc()
            create_task(doc, title="Check sim", project="ops", details="", created_by="discord")
            save_tasks(path, doc)
            loaded = load_tasks(path)
            self.assertEqual(len(loaded["tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
