import argparse
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from team_chat import auto_commit_changes, autocommit_opt_in_signal, teamchat_user_directed_signal  # noqa: E402


class TestTeamChatAutocommitContract(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> str:
        out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def _init_repo(self) -> Path:
        td = Path(tempfile.mkdtemp())
        self._git(td, "init")
        self._git(td, "config", "user.email", "tests@example.com")
        self._git(td, "config", "user.name", "TeamChat Tests")
        (td / "README.md").write_text("seed\n", encoding="utf-8")
        self._git(td, "add", "README.md")
        self._git(td, "commit", "-m", "seed")
        return td

    def test_default_signals_are_off(self):
        args = argparse.Namespace(allow_autocommit=False, user_directed_teamchat=False)
        self.assertEqual(autocommit_opt_in_signal(args), (False, "none"))
        self.assertEqual(teamchat_user_directed_signal(args), (False, "none"))

    def test_env_signals_are_recognized(self):
        args = argparse.Namespace(allow_autocommit=False, user_directed_teamchat=False)
        with patch.dict(os.environ, {"TEAMCHAT_ALLOW_AUTOCOMMIT": "1", "TEAMCHAT_USER_DIRECTED_TEAMCHAT": "1"}, clear=False):
            self.assertEqual(autocommit_opt_in_signal(args), (True, "env:TEAMCHAT_ALLOW_AUTOCOMMIT"))
            self.assertEqual(teamchat_user_directed_signal(args), (True, "env:TEAMCHAT_USER_DIRECTED_TEAMCHAT"))

    def test_no_opt_in_creates_no_commit(self):
        repo = self._init_repo()
        (repo / "README.md").write_text("seed\nchange\n", encoding="utf-8")
        before = self._git(repo, "rev-parse", "HEAD")

        sha, audit = auto_commit_changes(
            repo,
            "verify_teamchat_offline",
            1,
            autocommit_enabled=False,
            autocommit_signal="none",
            user_directed=True,
            user_directed_signal="cli:--user-directed-teamchat",
        )
        after = self._git(repo, "rev-parse", "HEAD")

        self.assertIsNone(sha)
        self.assertIsNone(audit)
        self.assertEqual(before, after)

    def test_opt_in_creates_commit_and_audit_artifact(self):
        repo = self._init_repo()
        (repo / "README.md").write_text("seed\nchange\n", encoding="utf-8")
        before = self._git(repo, "rev-parse", "HEAD")

        sha, audit = auto_commit_changes(
            repo,
            "verify_teamchat_offline",
            1,
            autocommit_enabled=True,
            autocommit_signal="cli:--allow-autocommit",
            user_directed=True,
            user_directed_signal="cli:--user-directed-teamchat",
        )
        after = self._git(repo, "rev-parse", "HEAD")

        self.assertIsNotNone(sha)
        self.assertNotEqual(before, after)
        self.assertTrue(audit)
        audit_path = repo / str(audit)
        self.assertTrue(audit_path.exists())
        body = audit_path.read_text(encoding="utf-8")
        self.assertIn("## Required Fields", body)
        self.assertIn("commit_sha:", body)
        self.assertIn("actor_mode:", body)
        self.assertIn("rationale:", body)
        self.assertIn("## Files Changed (name-status)", body)
        self.assertIn("## Commands Run + Outcomes", body)
        self.assertIn("## Cleanliness Evidence (git status)", body)
        self.assertIn("## Reproducibility", body)


if __name__ == "__main__":
    unittest.main()
