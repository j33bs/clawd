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

import team_chat  # noqa: E402


class _FakeRouter:
    def execute_with_escalation(self, intent, payload, context_metadata=None, validate_fn=None):
        return {
            "ok": True,
            "provider": "mock_provider",
            "model": "mock_model",
            "reason_code": "success",
            "attempts": 1,
            "text": "mock reply",
        }


class TestTeamChatNoSideEffects(unittest.TestCase):
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

    def test_flags_off_exits_without_runtime_writes_or_commits(self):
        repo = self._init_repo()
        before = self._git(repo, "rev-parse", "HEAD")
        args = argparse.Namespace(
            agents="planner,coder",
            session="flags_off",
            session_id="",
            output_root="",
            context_window=8,
            max_turns=2,
            message="hello team",
            once=True,
            user_directed_teamchat=False,
            allow_autocommit=False,
        )
        output_lines = []
        with patch.dict(os.environ, {"OPENCLAW_TEAMCHAT": "0"}, clear=False):
            rc = team_chat.run_multi_agent(
                args,
                repo_root=repo,
                router=_FakeRouter(),
                input_fn=lambda _: "",
                output_fn=output_lines.append,
            )
        after = self._git(repo, "rev-parse", "HEAD")

        self.assertEqual(rc, 2)
        self.assertEqual(before, after)
        self.assertFalse((repo / "workspace" / "state_runtime" / "teamchat" / "sessions" / "flags_off.jsonl").exists())
        self.assertTrue(any("OPENCLAW_TEAMCHAT=1" in line for line in output_lines))


if __name__ == "__main__":
    unittest.main()
