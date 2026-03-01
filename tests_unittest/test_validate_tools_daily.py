import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "tooling_health" / "validate_tools_daily.py"


class TestValidateToolsDaily(unittest.TestCase):
    def test_failures_log_and_mark_offline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "workspace" / "state_runtime" / "tool_validation").mkdir(parents=True, exist_ok=True)

            targets = {
                "checks": [
                    {
                        "name": "pass_command",
                        "kind": "command",
                        "tool_id": "tool.pass",
                        "command": ["python3", "-c", "print('ok')"],
                    },
                    {
                        "name": "fail_command",
                        "kind": "command",
                        "tool_id": "tool.fail",
                        "command": ["python3", "-c", "import sys;sys.exit(9)"],
                    },
                ]
            }
            targets_path = root / "targets.json"
            targets_path.write_text(json.dumps(targets), encoding="utf-8")

            run = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--repo-root",
                    str(root),
                    "--targets",
                    str(targets_path),
                    "--offline-ttl-hours",
                    "12",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)

            state = json.loads(
                (root / "workspace" / "state_runtime" / "tool_validation" / "offline_tools.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("tool.fail", state.get("offline", {}))
            self.assertNotIn("tool.pass", state.get("offline", {}))

            notice = (
                root / "workspace" / "state_runtime" / "tool_validation" / "heartbeat_notice.md"
            ).read_text(encoding="utf-8")
            self.assertIn("tool.fail", notice)

            error_log = (
                root / "workspace" / "state_runtime" / "tool_validation" / "tool_error.log"
            ).read_text(encoding="utf-8")
            self.assertIn("tool_id=tool.fail", error_log)
            self.assertIn("traceback:", error_log)


if __name__ == "__main__":
    unittest.main()
