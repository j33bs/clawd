import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "memory_distill_cron.py"


class TestMemoryDistillCron(unittest.TestCase):
    def test_distills_distinct_events_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory_dir = root / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            (root / "workspace" / "state_runtime" / "memory").mkdir(parents=True, exist_ok=True)
            (root / "MEMORY.md").write_text("# MEMORY.md - Long-Term Context\n", encoding="utf-8")

            today = dt.date.today()
            yesterday = today - dt.timedelta(days=1)
            (memory_dir / f"{today.isoformat()}.md").write_text(
                "# Daily Memory\n\n## Actions\n- Fixed gateway crash loop\n- Fixed gateway crash loop\n- Rotated tokens\n",
                encoding="utf-8",
            )
            (memory_dir / f"{yesterday.isoformat()}.md").write_text(
                "# Daily Memory\n\n## Actions\n- Rotated tokens\n- Added watchdog timer\n",
                encoding="utf-8",
            )

            first = subprocess.run(
                ["python3", str(SCRIPT), "--repo-root", str(root), "--window-days", "2", "--max-items", "10"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            payload = json.loads(first.stdout.strip())
            self.assertTrue(payload["updated"])
            self.assertEqual(payload["added_events"], 3)

            memory_md = (root / "MEMORY.md").read_text(encoding="utf-8")
            self.assertIn("## Daily Distillations", memory_md)
            self.assertIn("- Fixed gateway crash loop", memory_md)
            self.assertIn("- Rotated tokens", memory_md)
            self.assertIn("- Added watchdog timer", memory_md)

            second = subprocess.run(
                ["python3", str(SCRIPT), "--repo-root", str(root), "--window-days", "2", "--max-items", "10"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            payload_2 = json.loads(second.stdout.strip())
            self.assertFalse(payload_2["updated"])
            self.assertEqual(payload_2["added_events"], 0)


if __name__ == "__main__":
    unittest.main()
