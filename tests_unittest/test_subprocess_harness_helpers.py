"""Tests for workspace/local_exec/subprocess_harness.py pure helper functions.

Covers (no actual subprocess execution):
- _repo_realpath
- _ensure_within_repo
- resolve_repo_path
- _reject_shell_like
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_EXEC_DIR = REPO_ROOT / "workspace" / "local_exec"
if str(LOCAL_EXEC_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_EXEC_DIR))

from subprocess_harness import (  # noqa: E402
    SubprocessPolicyError,
    _reject_shell_like,
    resolve_repo_path,
)


# ---------------------------------------------------------------------------
# resolve_repo_path
# ---------------------------------------------------------------------------

class TestResolveRepoPath(unittest.TestCase):
    """Tests for resolve_repo_path() — validates and resolves relative paths."""

    def test_valid_relative_path_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = resolve_repo_path(root, "some/file.txt")
            self.assertIsInstance(result, Path)

    def test_absolute_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SubprocessPolicyError) as ctx:
                resolve_repo_path(Path(td), "/etc/passwd")
            self.assertIn("absolute", str(ctx.exception))

    def test_parent_ref_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SubprocessPolicyError) as ctx:
                resolve_repo_path(Path(td), "../escape")
            self.assertIn("parent_ref", str(ctx.exception))

    def test_empty_string_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SubprocessPolicyError) as ctx:
                resolve_repo_path(Path(td), "")
            self.assertIn("empty", str(ctx.exception))

    def test_whitespace_only_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SubprocessPolicyError):
                resolve_repo_path(Path(td), "   ")

    def test_must_exist_raises_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SubprocessPolicyError) as ctx:
                resolve_repo_path(Path(td), "nonexistent.txt", must_exist=True)
            self.assertIn("not_found", str(ctx.exception))

    def test_must_exist_ok_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "file.txt").write_text("x")
            result = resolve_repo_path(root, "file.txt", must_exist=True)
            self.assertTrue(result.exists())

    def test_resolved_path_within_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = resolve_repo_path(root, "sub/dir/file.py")
            # Use resolved root to handle macOS /var → /private/var symlink
            self.assertTrue(str(result).startswith(str(root.resolve())))


# ---------------------------------------------------------------------------
# _reject_shell_like
# ---------------------------------------------------------------------------

class TestRejectShellLike(unittest.TestCase):
    """Tests for _reject_shell_like() — rejects single-string shell commands."""

    def test_single_string_with_semicolon_rejected(self):
        with self.assertRaises(SubprocessPolicyError) as ctx:
            _reject_shell_like(["ls; rm -rf /"])
        self.assertIn("shell_like", str(ctx.exception))

    def test_single_string_with_ampersand_rejected(self):
        with self.assertRaises(SubprocessPolicyError):
            _reject_shell_like(["ls && echo bad"])

    def test_single_string_with_pipe_rejected(self):
        with self.assertRaises(SubprocessPolicyError):
            _reject_shell_like(["ls | head"])

    def test_single_string_with_dollar_rejected(self):
        with self.assertRaises(SubprocessPolicyError):
            _reject_shell_like(["echo $HOME"])

    def test_multi_arg_with_shell_chars_allowed(self):
        # Multiple args — only single-element list triggers check
        _reject_shell_like(["ls", "&&", "echo"])  # should NOT raise

    def test_clean_single_arg_allowed(self):
        _reject_shell_like(["ls"])  # no spaces or shell chars → ok

    def test_empty_argv_does_not_raise(self):
        # Only triggered for single element; empty list passes
        _reject_shell_like([])

    def test_backtick_in_single_arg_rejected(self):
        with self.assertRaises(SubprocessPolicyError):
            _reject_shell_like(["`whoami`"])


if __name__ == "__main__":
    unittest.main()
