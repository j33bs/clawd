import json
import tempfile
import unittest
from pathlib import Path
import importlib.util
import datetime as dt
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "memory_maintenance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("memory_maintenance", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MemoryMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_ensure_daily_memory_file_creates_structured_template(self):
        with tempfile.TemporaryDirectory() as td:
            memory_dir = Path(td) / "memory"
            target = dt.date(2026, 2, 26)

            path, created = self.mod.ensure_daily_memory_file(memory_dir, target)
            self.assertTrue(created)
            self.assertEqual(path.name, "2026-02-26.md")
            body = path.read_text(encoding="utf-8")
            self.assertIn("# Daily Memory - 2026-02-26", body)
            self.assertIn("## Context", body)
            self.assertIn("## Actions", body)
            self.assertIn("## Follow-ups", body)

            _, created_again = self.mod.ensure_daily_memory_file(memory_dir, target)
            self.assertFalse(created_again)

    def test_build_memory_index_emits_entries(self):
        with tempfile.TemporaryDirectory() as td:
            memory_dir = Path(td) / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "2026-02-25.md").write_text("# Daily Memory - 2026-02-25\n\nhello world\n", encoding="utf-8")
            (memory_dir / "2026-02-26.md").write_text("# Daily Memory - 2026-02-26\n\nsecond note\n", encoding="utf-8")

            output = Path(td) / "state" / "memory_index.json"
            payload = self.mod.build_memory_index(memory_dir, output)

            self.assertEqual(payload["total_files"], 2)
            self.assertTrue(output.exists())
            on_disk = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["total_files"], 2)
            self.assertEqual([entry["date"] for entry in on_disk["entries"]], ["2026-02-25", "2026-02-26"])

    def test_create_memory_snapshot_copies_daily_files_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_dir = root / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "2026-02-25.md").write_text("alpha\n", encoding="utf-8")
            (memory_dir / "2026-02-26.md").write_text("beta\n", encoding="utf-8")
            memory_md = root / "MEMORY.md"
            memory_md.write_text("# Long term\n", encoding="utf-8")

            snapshot_root = root / "workspace" / "state_runtime" / "memory" / "snapshots"
            result = self.mod.create_memory_snapshot(
                memory_dir,
                snapshot_root,
                label="test",
                include_paths=[memory_md],
            )

            self.assertTrue(result.snapshot_dir.exists())
            self.assertTrue((result.snapshot_dir / "2026-02-25.md").exists())
            self.assertTrue((result.snapshot_dir / "2026-02-26.md").exists())
            self.assertTrue((result.snapshot_dir / "MEMORY.md").exists())
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["file_count"], 3)


if __name__ == "__main__":
    unittest.main()
