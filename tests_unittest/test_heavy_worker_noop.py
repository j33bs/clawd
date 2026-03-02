import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "heavy_worker.py"


class TestHeavyWorkerNoop(unittest.TestCase):
    def test_worker_noop_when_contract_not_code(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = root / "current.json"
            contract.write_text('{"mode":"SERVICE","source":"TEST"}\n', encoding="utf-8")

            env = dict(os.environ)
            env["OPENCLAW_CONTRACT_CURRENT"] = str(contract)
            env["OPENCLAW_HEAVY_QUEUE_PATH"] = str(root / "heavy_jobs.jsonl")
            env["OPENCLAW_HEAVY_RUNS_LOG"] = str(root / "heavy_runs.jsonl")
            env["OPENCLAW_HEAVY_RUNS_DIR"] = str(root / "runs")
            env["OPENCLAW_CONTRACT_EVENTS"] = str(root / "events.jsonl")

            run = subprocess.run(
                [sys.executable, str(SCRIPT)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload.get("action"), "noop")
            self.assertIn("reason", payload)


if __name__ == "__main__":
    unittest.main()
