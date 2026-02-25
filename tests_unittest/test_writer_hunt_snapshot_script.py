import os
import stat
import subprocess
import unittest
from pathlib import Path


class TestWriterHuntSnapshotScript(unittest.TestCase):
    def test_script_exists_executable_and_has_headings(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "workspace" / "scripts" / "writer_hunt_snapshot.sh"
        self.assertTrue(script.exists())
        mode = script.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

        proc = subprocess.run(
            [str(script)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "OPENCLAW_QUIESCE": "1"},
        )
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        self.assertIn("=== writer_hunt_snapshot ===", output)
        self.assertIn("--- git_status_porcelain ---", output)
        self.assertIn("--- ps_filtered ---", output)
        self.assertIn("--- launchctl_filtered ---", output)


if __name__ == "__main__":
    unittest.main()
