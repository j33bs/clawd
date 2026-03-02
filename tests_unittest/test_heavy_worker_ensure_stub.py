import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "heavy_queue.py"
WORKER_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "heavy_worker.py"


class TestHeavyWorkerEnsureStub(unittest.TestCase):
    def test_worker_ensure_path_uses_stub_and_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            queue_path = base / "heavy_jobs.jsonl"
            runs_log = base / "heavy_runs.jsonl"
            runs_dir = base / "runs"
            events_path = base / "events.jsonl"
            contract_path = base / "current.json"
            contract_path.write_text('{"mode":"CODE","source":"TEST"}\n', encoding="utf-8")

            stub = base / "ensure_stub.py"
            stub.write_text("import sys\nprint('{\\\"ok\\\": false, \\\"offline_class\\\": \\\"POLICY\\\", \\\"reason\\\": \\\"stub_fail\\\"}')\nsys.exit(2)\n", encoding="utf-8")

            env = dict(os.environ)
            env["OPENCLAW_HEAVY_QUEUE_PATH"] = str(queue_path)
            env["OPENCLAW_HEAVY_RUNS_LOG"] = str(runs_log)
            env["OPENCLAW_HEAVY_RUNS_DIR"] = str(runs_dir)
            env["OPENCLAW_CONTRACT_EVENTS"] = str(events_path)
            env["OPENCLAW_CONTRACT_CURRENT"] = str(contract_path)
            env["OPENCLAW_ENSURE_CODER_PATH"] = str(stub)

            enqueue = subprocess.run(
                [sys.executable, str(QUEUE_SCRIPT), "enqueue", "--cmd", "echo heavy", "--requires-gpu"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(enqueue.returncode, 0, enqueue.stdout + enqueue.stderr)

            run = subprocess.run(
                [sys.executable, str(WORKER_SCRIPT)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                cwd=str(REPO_ROOT),
            )
            self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload.get("action"), "ensure_failed")

            rows = [json.loads(x) for x in runs_log.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertTrue(rows)
            self.assertEqual(rows[-1].get("status"), "ensure_failed")


if __name__ == "__main__":
    unittest.main()
