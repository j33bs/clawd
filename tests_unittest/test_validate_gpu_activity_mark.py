import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


class ValidateGpuActivityMarkTest(unittest.TestCase):
    def test_validator_marks_last_activity_for_coder_when_ok(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        validator = root / "skills" / "tooling_health" / "validate_tools_daily.py"

        with tempfile.TemporaryDirectory() as td:
            td_path = pathlib.Path(td)
            targets = td_path / "targets.json"
            targets.write_text(
                json.dumps(
                    {
                        "checks": [
                            {
                                "name": "coder_cmd_ok",
                                "tool_id": "coder_vllm.models",
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

            proc = subprocess.run(
                [
                    sys.executable,
                    str(validator),
                    "--repo-root",
                    str(td_path),
                    "--targets",
                    str(targets),
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

            last = td_path / "workspace" / "state_runtime" / "gpu" / "last_activity.json"
            self.assertTrue(last.exists())
            payload = json.loads(last.read_text(encoding="utf-8"))
            row = payload.get("coder_vllm.models") or {}
            self.assertEqual(row.get("source"), "validator_ok")
            self.assertTrue(str(row.get("ts", "")).endswith("Z"))


if __name__ == "__main__":
    unittest.main()
