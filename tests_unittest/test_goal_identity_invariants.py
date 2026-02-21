import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestGoalIdentityInvariants(unittest.TestCase):
    def test_verifier_passes_in_repo(self):
        repo_root = Path(__file__).resolve().parents[1]
        verifier = repo_root / "workspace" / "scripts" / "verify_goal_identity_invariants.py"
        self.assertTrue(verifier.exists(), str(verifier))

        p = subprocess.run(
            ["python3", str(verifier)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)

    def test_verifier_strict_fails_on_fixture_warning(self):
        repo_root = Path(__file__).resolve().parents[1]
        verifier = repo_root / "workspace" / "scripts" / "verify_goal_identity_invariants.py"
        self.assertTrue(verifier.exists(), str(verifier))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            # Minimal governance docs with required strings.
            gov = root / "workspace" / "governance"
            gov.mkdir(parents=True, exist_ok=True)
            (gov / "SECURITY_GOVERNANCE_CONTRACT.md").write_text(
                "C_Lawd\nTACTI(C)-R\nSystem Regulation\n", encoding="utf-8"
            )
            (gov / "GOAL_ANCHOR.md").write_text(
                "C_Lawd\nTACTI(C)-R\nSystem Regulation\n", encoding="utf-8"
            )
            (gov / "ASPIRATIONS_THREAT_MODEL.md").write_text("ok\n", encoding="utf-8")

            # Minimal policy with required ladder.
            pol = root / "workspace" / "policy"
            pol.mkdir(parents=True, exist_ok=True)
            ladder = ["google-gemini-cli", "qwen-portal", "groq", "ollama"]
            policy = {
                "routing": {
                    "free_order": ladder,
                    "intents": {
                        "system2_audit": {"order": ladder, "allowPaid": False},
                        "governance": {"order": ladder, "allowPaid": False},
                        "security": {"order": ladder, "allowPaid": False},
                    },
                }
            }
            (pol / "llm_policy.json").write_text(
                json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            # Minimal canonical models with required providers and invariants.
            models_dir = root / "agents" / "main" / "agent"
            models_dir.mkdir(parents=True, exist_ok=True)
            models = {
                "providers": {
                    "google-gemini-cli": {},
                    "qwen-portal": {},
                    "groq": {"baseUrl": "https://api.groq.ai/openai/v1"},
                    "ollama": {"baseUrl": "http://127.0.0.1:11434/v1"},
                }
            }
            (models_dir / "models.json").write_text(
                json.dumps(models, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            # Create a tracked file containing a bypass pattern (child_process use).
            # Make it tracked so the verifier's git ls-files scan includes it.
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "scripts" / "bad.js").write_text(
                "const child_process = require('child_process');\nchild_process.exec('echo hi');\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=str(root),
                check=True,
                capture_output=True,
                text=True,
                env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
            )

            # Non-strict mode: warnings allowed, exit 0.
            p_ok = subprocess.run(
                ["python3", str(verifier), "--repo-root", str(root)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p_ok.returncode, 0, p_ok.stdout + "\n" + p_ok.stderr)

            # Strict mode: warnings become failure.
            p_strict = subprocess.run(
                ["python3", str(verifier), "--repo-root", str(root), "--strict"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(p_strict.returncode, 0, p_strict.stdout + "\n" + p_strict.stderr)

    def test_verifier_syncs_repo_root_soul_mirror(self):
        repo_root = Path(__file__).resolve().parents[1]
        verifier = repo_root / "workspace" / "scripts" / "verify_goal_identity_invariants.py"
        self.assertTrue(verifier.exists(), str(verifier))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            gov = root / "workspace" / "governance"
            gov.mkdir(parents=True, exist_ok=True)
            canonical_soul = "Canonical soul line\n"
            (gov / "SOUL.md").write_text(canonical_soul, encoding="utf-8")
            (gov / "SECURITY_GOVERNANCE_CONTRACT.md").write_text(
                "C_Lawd\nTACTI(C)-R\nSystem Regulation\n", encoding="utf-8"
            )
            (gov / "GOAL_ANCHOR.md").write_text(
                "C_Lawd\nTACTI(C)-R\nSystem Regulation\n", encoding="utf-8"
            )
            (gov / "ASPIRATIONS_THREAT_MODEL.md").write_text("ok\n", encoding="utf-8")

            # Repo-root mirror starts diverged; verifier should sync from canonical.
            (root / "SOUL.md").write_text("Diverged soul line\n", encoding="utf-8")

            pol = root / "workspace" / "policy"
            pol.mkdir(parents=True, exist_ok=True)
            ladder = ["google-gemini-cli", "qwen-portal", "groq", "ollama"]
            policy = {
                "routing": {
                    "free_order": ladder,
                    "intents": {
                        "system2_audit": {"order": ladder, "allowPaid": False},
                        "governance": {"order": ladder, "allowPaid": False},
                        "security": {"order": ladder, "allowPaid": False},
                    },
                }
            }
            (pol / "llm_policy.json").write_text(
                json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            models_dir = root / "agents" / "main" / "agent"
            models_dir.mkdir(parents=True, exist_ok=True)
            models = {
                "providers": {
                    "google-gemini-cli": {},
                    "qwen-portal": {},
                    "groq": {"baseUrl": "https://api.groq.ai/openai/v1"},
                    "ollama": {"baseUrl": "http://127.0.0.1:11434/v1"},
                }
            }
            (models_dir / "models.json").write_text(
                json.dumps(models, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=str(root),
                check=True,
                capture_output=True,
                text=True,
                env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
            )

            p = subprocess.run(
                ["python3", str(verifier), "--repo-root", str(root)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)
            self.assertEqual((root / "SOUL.md").read_text(encoding="utf-8"), canonical_soul)


if __name__ == "__main__":
    unittest.main()
