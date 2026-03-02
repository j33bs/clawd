import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "heavy_queue.py"


class TestHeavyQueueRequiresGpu(unittest.TestCase):
    def test_enqueue_requires_gpu_sets_default_tool(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["OPENCLAW_HEAVY_QUEUE_PATH"] = str(Path(td) / "heavy_jobs.jsonl")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "enqueue", "--cmd", "echo hi", "--requires-gpu"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            payload = json.loads(run.stdout)
            self.assertTrue(payload["requires_gpu"])
            self.assertEqual(payload["tool_id"], "coder_vllm.models")

    def test_enqueue_defaults_non_gpu(self):
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["OPENCLAW_HEAVY_QUEUE_PATH"] = str(Path(td) / "heavy_jobs.jsonl")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "enqueue", "--cmd", "echo hi"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            payload = json.loads(run.stdout)
            self.assertFalse(payload["requires_gpu"])
            self.assertIsNone(payload.get("tool_id"))


if __name__ == "__main__":
    unittest.main()
