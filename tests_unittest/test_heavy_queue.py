import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "heavy_queue.py"


class TestHeavyQueue(unittest.TestCase):
    def test_enqueue_outputs_deterministic_job(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["OPENCLAW_HEAVY_QUEUE_PATH"] = str(Path(td) / "heavy_jobs.jsonl")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "enqueue", "--cmd", "echo hello"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["state"], "queued")
            self.assertEqual(payload["cmd"], "echo hello")
            self.assertEqual(payload["schema"], 1)


if __name__ == "__main__":
    unittest.main()
