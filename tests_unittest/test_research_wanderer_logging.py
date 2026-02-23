import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestResearchWandererLogging(unittest.TestCase):
    def test_wander_session_appends_required_jsonl_fields(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "workspace" / "scripts" / "research_wanderer.py"
        with tempfile.TemporaryDirectory() as td:
            troot = Path(td)
            oq = troot / "OPEN_QUESTIONS.md"
            oq.write_text("# Open Questions\n\n", encoding="utf-8")
            payload = troot / "payload.json"
            payload.write_text(
                json.dumps(
                    [
                        {"question": "How should memory routing adapt?", "significance": 0.91},
                        {"question": "What uncertainty remains after synthesis?", "significance": 0.84},
                    ]
                ),
                encoding="utf-8",
            )
            log_path = troot / "wander_log.jsonl"

            proc = subprocess.run(
                [
                    "python3",
                    str(script),
                    "--input",
                    str(payload),
                    "--open-questions-path",
                    str(oq),
                    "--wander-log-path",
                    str(log_path),
                    "--session-id",
                    "sess-001",
                    "--trigger",
                    "manual",
                    "--json",
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            row = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            for key in (
                "timestamp",
                "session_id",
                "trigger",
                "inquiry_momentum_score",
                "threshold",
                "exceeded",
                "duration_ms",
                "trails_written_count",
                "errors",
            ):
                self.assertIn(key, row)

    def test_wander_log_failure_does_not_break_run(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "workspace" / "scripts" / "research_wanderer.py"
        with tempfile.TemporaryDirectory() as td:
            troot = Path(td)
            oq = troot / "OPEN_QUESTIONS.md"
            oq.write_text("# Open Questions\n\n", encoding="utf-8")
            bad_log_path = troot / "logdir"
            bad_log_path.mkdir(parents=True, exist_ok=True)

            proc = subprocess.run(
                [
                    "python3",
                    str(script),
                    "--question",
                    "What is the next inquiry?",
                    "--open-questions-path",
                    str(oq),
                    "--wander-log-path",
                    str(bad_log_path),
                    "--json",
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            out = json.loads(proc.stdout)
            self.assertIn("wander_log_warning", out)


if __name__ == "__main__":
    unittest.main()

