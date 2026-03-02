import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "contract_policy.py"


class TestContractPolicy(unittest.TestCase):
    def test_gpu_allowed_false_in_service_mode(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current.json"
            current.write_text('{"mode":"SERVICE","source":"TEST"}\n', encoding="utf-8")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "gpu-allowed", "--tool-id", "coder_vllm.models", "--contract", str(current)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0)
            payload = json.loads(run.stdout)
            self.assertFalse(payload["allowed"])
            self.assertEqual(payload["reason"], "policy_service_or_idle")

    def test_gpu_allowed_true_when_mode_code(self):
        with tempfile.TemporaryDirectory() as td:
            current = Path(td) / "current.json"
            current.write_text('{"mode":"CODE","source":"TEST"}\n', encoding="utf-8")
            env = dict(os.environ)
            env["OPENCLAW_CONTRACT_CURRENT"] = str(current)
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "gpu-allowed", "--tool-id", "coder_vllm.models"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(run.returncode, 0)
            payload = json.loads(run.stdout)
            self.assertTrue(payload["allowed"])
            self.assertEqual(payload["reason"], "mode_code")


if __name__ == "__main__":
    unittest.main()
