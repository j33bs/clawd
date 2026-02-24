import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "verify_openclaw_tmp_logrotate.sh"


class TmpLogrotateDryRunTests(unittest.TestCase):
    def test_logrotate_dryrun_script(self):
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        text = proc.stdout + proc.stderr
        self.assertTrue(
            ("PASS: openclaw tmp logrotate dry-run" in text) or ("SKIP: logrotate not found on PATH" in text),
            msg=text,
        )


if __name__ == "__main__":
    unittest.main()
