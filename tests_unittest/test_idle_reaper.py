import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


class IdleReaperTest(unittest.TestCase):
    def test_idle_reaper_runs_noop_when_service_not_active(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            td_path = pathlib.Path(td)
            env = os.environ.copy()
            env["OPENCLAW_GPU_STATE_DIR"] = str(td_path / "gpu")
            env["OPENCLAW_CONTRACT_CURRENT"] = str(td_path / "contract" / "current.json")
            env["OPENCLAW_CONTRACT_EVENTS"] = str(td_path / "contract" / "events.jsonl")
            env["OPENCLAW_IDLE_REAPER_FORCE_SERVICE_INACTIVE"] = "1"

            proc = subprocess.run(
                [sys.executable, "workspace/scripts/idle_reaper.py"],
                cwd=str(root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout.strip() or "{}")
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("reason"), "service_not_active")
            events_path = td_path / "contract" / "events.jsonl"
            self.assertTrue(events_path.exists())
            lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 1)
            event = json.loads(lines[-1])
            self.assertEqual(event.get("type"), "idle_reaper_action")
            self.assertEqual(event.get("reason"), "service_not_active")


if __name__ == "__main__":
    unittest.main()
