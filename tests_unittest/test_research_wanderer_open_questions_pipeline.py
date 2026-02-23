import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestResearchWandererOpenQuestionsPipeline(unittest.TestCase):
    def test_append_preserves_append_only_guard(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "workspace" / "scripts" / "research_wanderer.py"
        guard = repo_root / "workspace" / "scripts" / "hooks" / "guard_open_questions_append_only.sh"
        self.assertTrue(script.exists())
        self.assertTrue(guard.exists())

        with tempfile.TemporaryDirectory() as td:
            troot = Path(td)
            (troot / "workspace").mkdir(parents=True, exist_ok=True)
            oq = troot / "workspace" / "OPEN_QUESTIONS.md"
            oq.write_text("# Open Questions\n\n1. Existing question\n", encoding="utf-8")

            payload = [
                {"question": "How should routing adapt?", "significance": 0.91},
                {"question": "Token ABCDEFGHIJKLMNOPQRSTUVWX12345", "significance": 0.87},
            ]
            in_path = troot / "payload.json"
            in_path.write_text(json.dumps(payload), encoding="utf-8")

            subprocess.run(["git", "init"], cwd=troot, check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "workspace/OPEN_QUESTIONS.md"], cwd=troot, check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init"],
                cwd=troot,
                check=True,
                capture_output=True,
                text=True,
            )

            p = subprocess.run(
                [
                    "python3",
                    str(script),
                    "--input",
                    str(in_path),
                    "--open-questions-path",
                    str(oq),
                    "--run-id",
                    "rw-test",
                    "--json",
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)

            content = oq.read_text(encoding="utf-8")
            self.assertIn("Research Wanderer Session", content)
            self.assertIn("[REDACTED_TOKEN]", content)

            subprocess.run(["git", "add", "workspace/OPEN_QUESTIONS.md"], cwd=troot, check=True, capture_output=True, text=True)
            g = subprocess.run(["bash", str(guard)], cwd=troot, capture_output=True, text=True, check=False)
            self.assertEqual(g.returncode, 0, g.stdout + "\n" + g.stderr)


if __name__ == "__main__":
    unittest.main()
