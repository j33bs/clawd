import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestDispositionalProbeLog(unittest.TestCase):
    def test_append_only_jsonl(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "workspace" / "scripts" / "run_dispositional_probe.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "dispositional_log.jsonl"
            cmd = [
                "python3",
                str(script),
                "--log-path",
                str(log_path),
                "--session-id",
                "sess1",
                "--response",
                "a",
            ]
            p1 = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=False)
            self.assertEqual(p1.returncode, 0, p1.stdout + p1.stderr)

            cmd2 = [
                "python3",
                str(script),
                "--log-path",
                str(log_path),
                "--session-id",
                "sess2",
                "--response",
                "b",
            ]
            p2 = subprocess.run(cmd2, cwd=str(repo_root), capture_output=True, text=True, check=False)
            self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["session_id"], "sess1")
            self.assertEqual(second["session_id"], "sess2")
            self.assertEqual(len(first["responses"]), 12)
            self.assertEqual(len(second["responses"]), 12)


if __name__ == "__main__":
    unittest.main()
