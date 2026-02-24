import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "verify_runtime_autoupdate.sh"


class RuntimeAutoupdateGateTests(unittest.TestCase):
    def test_runtime_autoupdate_dryrun_includes_health_gate(self):
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("ok: runtime autoupdate dry-run verified", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
