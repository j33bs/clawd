import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from diagnose_openclaw_status_hang import diagnose  # noqa: E402


class TestDiagnoseOpenClawStatusHang(unittest.TestCase):
    def test_reports_missing_openclaw_binary(self):
        notes = diagnose([], has_openclaw=False)
        self.assertTrue(any("binary not found" in note for note in notes))

    def test_reports_gateway_loaded_but_not_listening(self):
        results = [
            {"command": "openclaw status", "timed_out": False, "stdout": "", "stderr": "", "exit_code": 0},
            {"command": "openclaw status --deep", "timed_out": False, "stdout": "", "stderr": "", "exit_code": 0},
            {"command": "openclaw status --json", "timed_out": False, "stdout": "", "stderr": "", "exit_code": 0},
            {
                "command": "openclaw gateway status",
                "timed_out": False,
                "exit_code": 0,
                "stdout": (
                    "Service: LaunchAgent (loaded)\n"
                    "Gateway port 18789 is not listening (service appears running).\n"
                    "Last gateway error: Gateway start blocked: set gateway.mode=local (current: unset)\n"
                ),
                "stderr": "",
            },
        ]
        notes = diagnose(results, has_openclaw=True)
        self.assertTrue(any("loaded but not listening" in note for note in notes))
        self.assertTrue(any("set gateway.mode=local" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
