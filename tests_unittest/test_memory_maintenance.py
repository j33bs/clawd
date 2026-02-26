import json
import tempfile
import unittest
from pathlib import Path
import importlib.util
import datetime as dt
import sys
import os


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

    def test_consolidate_memory_fragments_deduplicates_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_dir = root / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "2026-02-25.md").write_text(
                "# Daily Memory - 2026-02-25\n\n## Actions\n- fix queue bug\n- fix queue bug\n",
                encoding="utf-8",
            )
            (memory_dir / "2026-02-26.md").write_text(
                "# Daily Memory - 2026-02-26\n\n## Follow-ups\n- add retry tests\n",
                encoding="utf-8",
            )
            output = root / "workspace" / "state_runtime" / "memory" / "heartbeat_consolidation.json"

            first = self.mod.consolidate_memory_fragments(
                memory_dir,
                output,
                today=dt.date(2026, 2, 26),
                window_days=2,
            )
            self.assertTrue(first["changed"])
            self.assertEqual(first["consolidated_count"], 2)

            second = self.mod.consolidate_memory_fragments(
                memory_dir,
                output,
                today=dt.date(2026, 2, 26),
                window_days=2,
            )
            self.assertFalse(second["changed"])
            self.assertEqual(second["consolidated_count"], 2)

    def test_distill_weekly_memory_updates_once_per_week_and_migrates_old_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_dir = root / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (memory_dir / "2026-02-20.md").write_text(
                "# Daily Memory - 2026-02-20\n\n## Actions\n- stabilized runtime overlay\n",
                encoding="utf-8",
            )
            (memory_dir / "2026-02-25.md").write_text(
                "# Daily Memory - 2026-02-25\n\n## Follow-ups\n- verify telegram reply mode\n",
                encoding="utf-8",
            )
            memory_md = root / "MEMORY.md"
            memory_md.write_text("# MEMORY.md - Long-Term Context\n\n", encoding="utf-8")
            state_path = root / "workspace" / "state_runtime" / "memory" / "weekly_distill_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(["2026-W07"]), encoding="utf-8")

            result = self.mod.distill_weekly_memory(
                memory_dir,
                memory_md,
                state_path,
                today=dt.date(2026, 2, 26),
            )
            self.assertTrue(result["updated"])
            body = memory_md.read_text(encoding="utf-8")
            self.assertIn("## Weekly Distillations", body)
            self.assertIn("### 2026-W09 (2026-02-26)", body)

            second = self.mod.distill_weekly_memory(
                memory_dir,
                memory_md,
                state_path,
                today=dt.date(2026, 2, 26),
            )
            self.assertFalse(second["updated"])
            self.assertEqual(second["reason"], "already_distilled")

    def test_cleanup_forgotten_memory_files_archives_old_daily_and_prunes_stale_empty_archive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_dir = root / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            recent = memory_dir / "2026-02-25.md"
            old = memory_dir / "2025-12-01.md"
            recent.write_text("recent\n", encoding="utf-8")
            old.write_text("old\n", encoding="utf-8")

            archive_root = memory_dir / "archive"
            stale_empty = archive_root / "2025" / "forgotten-empty.md"
            stale_empty.parent.mkdir(parents=True, exist_ok=True)
            stale_empty.write_text("", encoding="utf-8")
            old_epoch = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp()
            os.utime(stale_empty, (old_epoch, old_epoch))

            result = self.mod.cleanup_forgotten_memory_files(
                memory_dir,
                archive_root,
                today=dt.date(2026, 2, 26),
                retain_days=30,
                archive_prune_days=365,
            )

            self.assertEqual(result["moved_count"], 1)
            self.assertTrue((archive_root / "2025" / "2025-12-01.md").exists())
            self.assertTrue(recent.exists())
            self.assertEqual(result["pruned_count"], 1)
            self.assertFalse(stale_empty.exists())


if __name__ == "__main__":
    unittest.main()
