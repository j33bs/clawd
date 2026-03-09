"""Tests for pure helpers in workspace/scripts/team_chat_adapters.py.

Covers:
- _contains_shell_metacharacters(cmd) — regex safety check
- _is_allowed_command(cmd, extra_patterns) — allowlist gate
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import team_chat_adapters as _tca  # noqa: E402

_contains_shell_metacharacters = _tca._contains_shell_metacharacters
_is_allowed_command = _tca._is_allowed_command


# ---------------------------------------------------------------------------
# _contains_shell_metacharacters
# ---------------------------------------------------------------------------


class TestContainsShellMetacharacters(unittest.TestCase):
    """Tests for _contains_shell_metacharacters() — detects shell injection chars."""

    def test_plain_command_false(self):
        self.assertFalse(_contains_shell_metacharacters("git status"))

    def test_pipe_returns_true(self):
        self.assertTrue(_contains_shell_metacharacters("cat file | grep foo"))

    def test_semicolon_returns_true(self):
        self.assertTrue(_contains_shell_metacharacters("echo hi; rm -rf /"))

    def test_ampersand_returns_true(self):
        self.assertTrue(_contains_shell_metacharacters("sleep 10 & ls"))

    def test_backtick_returns_true(self):
        self.assertTrue(_contains_shell_metacharacters("echo `whoami`"))

    def test_redirect_gt_returns_true(self):
        self.assertTrue(_contains_shell_metacharacters("echo hi > /tmp/out"))

    def test_redirect_lt_returns_true(self):
        self.assertTrue(_contains_shell_metacharacters("sort < input.txt"))

    def test_empty_string_false(self):
        self.assertFalse(_contains_shell_metacharacters(""))

    def test_returns_bool(self):
        self.assertIsInstance(_contains_shell_metacharacters("git status"), bool)

    def test_path_with_slash_false(self):
        self.assertFalse(_contains_shell_metacharacters("python3 workspace/scripts/foo.py"))


# ---------------------------------------------------------------------------
# _is_allowed_command
# ---------------------------------------------------------------------------


class TestIsAllowedCommand(unittest.TestCase):
    """Tests for _is_allowed_command() — allowlist gate against ALLOWED_COMMAND_PATTERNS."""

    def test_git_status_allowed(self):
        self.assertTrue(_is_allowed_command("git status"))

    def test_git_diff_allowed(self):
        self.assertTrue(_is_allowed_command("git diff"))

    def test_git_log_allowed(self):
        self.assertTrue(_is_allowed_command("git log"))

    def test_unknown_command_blocked(self):
        self.assertFalse(_is_allowed_command("rm -rf /"))

    def test_metacharacter_command_blocked(self):
        self.assertFalse(_is_allowed_command("git status; rm -rf /"))

    def test_empty_string_blocked(self):
        self.assertFalse(_is_allowed_command(""))

    def test_whitespace_only_blocked(self):
        self.assertFalse(_is_allowed_command("   "))

    def test_npm_test_allowed(self):
        self.assertTrue(_is_allowed_command("npm test"))

    def test_extra_pattern_extends_allowlist(self):
        result = _is_allowed_command("my-custom-tool", extra_patterns=[r"^my-custom-tool(\s|$)"])
        self.assertTrue(result)

    def test_returns_bool(self):
        self.assertIsInstance(_is_allowed_command("git status"), bool)


if __name__ == "__main__":
    unittest.main()
