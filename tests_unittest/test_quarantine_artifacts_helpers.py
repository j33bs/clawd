"""Tests for pure helpers in workspace/scripts/quarantine_artifacts.py.

Stubs subprocess.run to avoid real git calls.

Covers:
- list_untracked() — parses git status --porcelain output
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
QA_PATH = REPO_ROOT / "workspace" / "scripts" / "quarantine_artifacts.py"

_spec = _ilu.spec_from_file_location("quarantine_artifacts_real", str(QA_PATH))
qa = _ilu.module_from_spec(_spec)
sys.modules["quarantine_artifacts_real"] = qa
_spec.loader.exec_module(qa)


def _mock_git_output(entries: list) -> MagicMock:
    """Build a subprocess.run mock that returns null-separated porcelain output."""
    # git status --porcelain=v1 -z: each entry is 'XY path\x00'
    parts = [e.encode() for e in entries]
    stdout = b"\x00".join(parts)
    mock = MagicMock()
    mock.stdout = stdout
    return mock


# ---------------------------------------------------------------------------
# list_untracked
# ---------------------------------------------------------------------------

class TestListUntracked(unittest.TestCase):
    """Tests for list_untracked() — parses git porcelain output."""

    def test_returns_list(self):
        with patch("subprocess.run", return_value=_mock_git_output([])):
            result = qa.list_untracked()
        self.assertIsInstance(result, list)

    def test_empty_when_no_untracked(self):
        with patch("subprocess.run", return_value=_mock_git_output([])):
            result = qa.list_untracked()
        self.assertEqual(result, [])

    def test_returns_untracked_file(self):
        with patch("subprocess.run", return_value=_mock_git_output(["?? somefile.py"])):
            result = qa.list_untracked()
        self.assertIn("somefile.py", result)

    def test_ignores_tracked_modified(self):
        # " M" = modified in working tree — not untracked
        with patch("subprocess.run", return_value=_mock_git_output([" M tracked.py"])):
            result = qa.list_untracked()
        self.assertEqual(result, [])

    def test_ignores_staged_files(self):
        # "M " = staged modification — not untracked
        with patch("subprocess.run", return_value=_mock_git_output(["M  staged.py"])):
            result = qa.list_untracked()
        self.assertEqual(result, [])

    def test_multiple_untracked(self):
        with patch("subprocess.run", return_value=_mock_git_output([
            "?? file_a.txt",
            "?? file_b.txt",
        ])):
            result = qa.list_untracked()
        self.assertIn("file_a.txt", result)
        self.assertIn("file_b.txt", result)
        self.assertEqual(len(result), 2)

    def test_mixed_tracked_and_untracked(self):
        with patch("subprocess.run", return_value=_mock_git_output([
            " M modified.py",
            "?? new_file.py",
        ])):
            result = qa.list_untracked()
        self.assertEqual(result, ["new_file.py"])

    def test_skips_empty_entries(self):
        """Null-split may produce empty byte strings — those are skipped."""
        mock = MagicMock()
        mock.stdout = b"?? only.py\x00\x00"
        with patch("subprocess.run", return_value=mock):
            result = qa.list_untracked()
        self.assertEqual(result, ["only.py"])

    def test_handles_none_stdout(self):
        mock = MagicMock()
        mock.stdout = None
        with patch("subprocess.run", return_value=mock):
            result = qa.list_untracked()
        self.assertEqual(result, [])

    def test_path_stripped_of_status_prefix(self):
        """Entry '?? workspace/tmp/foo.py' → path is 'workspace/tmp/foo.py'."""
        with patch("subprocess.run", return_value=_mock_git_output([
            "?? workspace/tmp/foo.py",
        ])):
            result = qa.list_untracked()
        self.assertEqual(result, ["workspace/tmp/foo.py"])


if __name__ == "__main__":
    unittest.main()
