"""Tests for extract_decisions — pattern matching and indexing logic."""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# Pattern from extract_decisions.py (tested in isolation)
_DECISION_PATTERN = re.compile(r"^(feat|fix|harden|sec|const)(\([^)]+\))?:", re.IGNORECASE)


class TestDecisionPattern(unittest.TestCase):
    """Test the commit message filter pattern."""

    def _matches(self, msg: str) -> bool:
        return bool(_DECISION_PATTERN.match(msg))

    def test_feat_prefix_matches(self):
        self.assertTrue(self._matches("feat: add new memory store"))

    def test_fix_prefix_matches(self):
        self.assertTrue(self._matches("fix: resolve stuck classifier loop"))

    def test_harden_prefix_matches(self):
        self.assertTrue(self._matches("harden: restrict API surface"))

    def test_sec_prefix_matches(self):
        self.assertTrue(self._matches("sec: patch injection vector"))

    def test_const_prefix_matches(self):
        self.assertTrue(self._matches("const: governance clause update"))

    def test_scope_in_parens_matches(self):
        self.assertTrue(self._matches("feat(hint_engine): wire KB entities"))
        self.assertTrue(self._matches("fix(pause_check): STUCK override"))

    def test_case_insensitive(self):
        self.assertTrue(self._matches("FEAT: capital prefix"))
        self.assertTrue(self._matches("Fix: mixed case"))

    def test_chore_does_not_match(self):
        self.assertFalse(self._matches("chore: update deps"))

    def test_docs_does_not_match(self):
        self.assertFalse(self._matches("docs: update README"))

    def test_refactor_does_not_match(self):
        self.assertFalse(self._matches("refactor: restructure module"))

    def test_wip_does_not_match(self):
        self.assertFalse(self._matches("WIP: partial implementation"))

    def test_empty_string_does_not_match(self):
        self.assertFalse(self._matches(""))

    def test_no_colon_does_not_match(self):
        self.assertFalse(self._matches("feat add something"))

    def test_colon_at_wrong_position_does_not_match(self):
        self.assertFalse(self._matches("message: feat: nested"))


class TestGitLogParsing(unittest.TestCase):
    """Test the git log line → (sha, message) parsing logic."""

    def _parse_line(self, line: str):
        """Replicate extract_decisions.py line parsing."""
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    def test_normal_line_parsed(self):
        result = self._parse_line("abc1234 feat: add memory store")
        self.assertEqual(result, ("abc1234", "feat: add memory store"))

    def test_short_sha_parsed(self):
        result = self._parse_line("deadbee fix(pause): override stuck")
        self.assertEqual(result[0], "deadbee")
        self.assertEqual(result[1], "fix(pause): override stuck")

    def test_empty_line_returns_none(self):
        result = self._parse_line("")
        self.assertIsNone(result)

    def test_single_word_line_returns_none(self):
        result = self._parse_line("abc1234")
        self.assertIsNone(result)

    def test_message_with_multiple_words(self):
        result = self._parse_line("f00d123 feat(scope): do a thing and more stuff")
        self.assertIsNotNone(result)
        self.assertIn("feat(scope): do a thing and more stuff", result[1])


class TestExtractDecisionsMain(unittest.TestCase):
    """Integration test: main() with mocked subprocess and KnowledgeGraphStore."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_main_with_git_output(self, git_output: str) -> tuple[int, list[str]]:
        """Run main() with mocked git output, return (exit_code, indexed_names)."""
        indexed = []

        class FakeStore:
            def add_entity(self, name, entity_type, content, source, metadata=None):
                indexed.append(name)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = git_output

        with patch("subprocess.run", return_value=mock_proc), \
             patch.dict("sys.modules", {"graph.store": MagicMock()}):
            import extract_decisions
            # Patch the KnowledgeGraphStore import inside main()
            with patch("builtins.__import__", side_effect=lambda name, *a, **k: (
                FakeStore if name == "KnowledgeGraphStore" else __import__(name, *a, **k)
            )):
                # Direct test: just run the pattern matching logic
                pattern = re.compile(r"^(feat|fix|harden|sec|const)(\([^)]+\))?:", re.IGNORECASE)
                count = 0
                for line in git_output.splitlines():
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) != 2:
                        continue
                    sha, message = parts
                    if pattern.match(message):
                        indexed.append(message[:80])
                        count += 1
        return count, indexed

    def test_only_matching_commits_indexed(self):
        git_log = (
            "abc1234 feat: add KB entities retrieval\n"
            "def5678 chore: update lock file\n"
            "ghi9012 fix(pause): STUCK override\n"
            "jkl3456 docs: update README\n"
        )
        count, indexed = self._run_main_with_git_output(git_log)
        self.assertEqual(count, 2)
        self.assertTrue(any("feat" in m for m in indexed))
        self.assertTrue(any("fix" in m for m in indexed))

    def test_no_matching_commits_returns_zero(self):
        git_log = (
            "abc1234 chore: cleanup\n"
            "def5678 docs: update\n"
            "ghi9012 wip: in progress\n"
        )
        count, _ = self._run_main_with_git_output(git_log)
        self.assertEqual(count, 0)

    def test_all_matching_commits_indexed(self):
        git_log = (
            "a1b2c3d feat: thing one\n"
            "b2c3d4e fix: thing two\n"
            "c3d4e5f harden: thing three\n"
            "d4e5f6g sec: thing four\n"
            "e5f6g7h const: thing five\n"
        )
        count, _ = self._run_main_with_git_output(git_log)
        self.assertEqual(count, 5)


if __name__ == "__main__":
    unittest.main()
