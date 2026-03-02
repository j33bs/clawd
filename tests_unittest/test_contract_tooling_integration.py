import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


class ContractToolingIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(__file__).resolve().parents[1]
        self.gpu_lock = self.root / "workspace" / "scripts" / "gpu_lock.py"
        self.ensure = self.root / "workspace" / "scripts" / "ensure_coder_vllm_up.py"
        self.validator = self.root / "skills" / "tooling_health" / "validate_tools_daily.py"

    def test_gpu_lock_claim_release(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["OPENCLAW_GPU_STATE_DIR"] = str(pathlib.Path(td) / "gpu")

            claim = subprocess.run(
                [sys.executable, str(self.gpu_lock), "claim", "--holder", "test", "--ttl-minutes", "1"],
                cwd=str(self.root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(claim.returncode, 0, claim.stderr)

            release = subprocess.run(
                [sys.executable, str(self.gpu_lock), "release", "--holder", "test"],
                cwd=str(self.root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(release.returncode, 0, release.stderr)

    def test_ensure_coder_policy_when_contract_not_code(self):
        with tempfile.TemporaryDirectory() as td:
            contract_path = pathlib.Path(td) / "current.json"
            contract_path.write_text(
                json.dumps({"mode": "SERVICE", "override": None}, indent=2) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["OPENCLAW_CONTRACT_CURRENT"] = str(contract_path)
            env["OPENCLAW_GPU_STATE_DIR"] = str(pathlib.Path(td) / "gpu")

            proc = subprocess.run(
                [sys.executable, str(self.ensure)],
                cwd=str(self.root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("offline_class"), "POLICY")
            self.assertEqual(payload.get("reason"), "contract_not_code")

    def test_validator_emits_contract_signal(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = pathlib.Path(td)
            targets = td_path / "targets.json"
            targets.write_text(
                json.dumps(
                    {
                        "checks": [
                            {
                                "name": "self_command_ok",
                                "tool_id": "test.command.ok",
                                "kind": "command",
                                "command": [sys.executable, "-c", "print('ok')"],
                                "timeout_sec": 5,
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            signal_file = td_path / "signals" / "activity.jsonl"
            env = os.environ.copy()
            env["OPENCLAW_CONTRACT_SIGNALS_PATH"] = str(signal_file)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(self.validator),
                    "--repo-root",
                    str(td_path),
                    "--targets",
                    str(targets),
                ],
                cwd=str(self.root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(signal_file.exists())
            lines = [line for line in signal_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 1)
            event = json.loads(lines[-1])
            self.assertEqual(event.get("kind"), "tool_call")
            self.assertEqual((event.get("meta") or {}).get("source"), "validate_tools_daily")


if __name__ == "__main__":
    unittest.main()
