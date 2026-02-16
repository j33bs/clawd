import subprocess
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


if __name__ == "__main__":
    unittest.main()

