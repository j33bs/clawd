"""Tests for workspace/memory/pattern_chunker.py pure helpers and shortcuts API.

Covers (no disk I/O beyond tempfile):
- PatternChunker._extract_template
- PatternChunker.list_shortcuts
- PatternChunker.create_shortcut
- PatternChunker.match_shortcut
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "workspace" / "memory"
if str(MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(MEMORY_DIR))

from pattern_chunker import PatternChunker  # noqa: E402


def _chunker(td: str) -> PatternChunker:
    """Build a PatternChunker backed by a temp dir with an empty shortcuts file."""
    sc = Path(td) / "shortcuts.json"
    sc.write_text('{"shortcuts": []}', encoding="utf-8")
    return PatternChunker(memory_dir=td, shortcuts_path=str(sc))


# ---------------------------------------------------------------------------
# _extract_template
# ---------------------------------------------------------------------------

class TestExtractTemplate(unittest.TestCase):
    """Tests for _extract_template() — numbers/paths/UUIDs → placeholders."""

    def test_numbers_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("run test 42")
            self.assertIn("<n>", result)
            self.assertNotIn("42", result)

    def test_paths_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("open /path/to/file.py")
            self.assertIn("<path>", result)

    def test_uuid_like_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("ref abc123def456")
            # Long hex replaced with <ID>
            self.assertNotIn("abc123def456", result)

    def test_lowercased(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("Run Test")
            self.assertEqual(result, result.lower())

    def test_stripped(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("  hello  ")
            self.assertFalse(result.startswith(" "))
            self.assertFalse(result.endswith(" "))

    def test_no_numbers_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("hello world")
            self.assertEqual(result, "hello world")

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            self.assertIsInstance(c._extract_template("test"), str)

    def test_empty_string(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c._extract_template("")
            self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# list_shortcuts
# ---------------------------------------------------------------------------

class TestListShortcuts(unittest.TestCase):
    """Tests for list_shortcuts() — returns list of shortcuts."""

    def test_empty_shortcuts_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c.list_shortcuts()
            self.assertIsInstance(result, list)

    def test_empty_shortcuts_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            self.assertEqual(c.list_shortcuts(), [])


# ---------------------------------------------------------------------------
# create_shortcut
# ---------------------------------------------------------------------------

class TestCreateShortcut(unittest.TestCase):
    """Tests for create_shortcut() — appends shortcut to shortcuts list."""

    def test_creates_shortcut_dict(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            sc = c.create_shortcut("run test <n>", "run-test", "Running test {n}")
            self.assertIsInstance(sc, dict)

    def test_shortcut_has_name(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            sc = c.create_shortcut("tmpl", "myname", "response")
            self.assertEqual(sc["name"], "myname")

    def test_shortcut_has_template(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            sc = c.create_shortcut("run test <n>", "n", "r")
            self.assertEqual(sc["template"], "run test <n>")

    def test_shortcut_appears_in_list(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            c.create_shortcut("tmpl", "sc1", "resp")
            shortcuts = c.list_shortcuts()
            self.assertEqual(len(shortcuts), 1)
            self.assertEqual(shortcuts[0]["name"], "sc1")

    def test_shortcut_persisted_to_file(self):
        with tempfile.TemporaryDirectory() as td:
            sc_path = Path(td) / "shortcuts.json"
            sc_path.write_text('{"shortcuts": []}', encoding="utf-8")
            c = PatternChunker(memory_dir=td, shortcuts_path=str(sc_path))
            c.create_shortcut("tmpl", "sc1", "resp")
            data = json.loads(sc_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["shortcuts"]), 1)

    def test_usage_count_starts_at_zero(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            sc = c.create_shortcut("tmpl", "n", "r")
            self.assertEqual(sc["usage_count"], 0)


# ---------------------------------------------------------------------------
# match_shortcut
# ---------------------------------------------------------------------------

class TestMatchShortcut(unittest.TestCase):
    """Tests for match_shortcut() — template matching."""

    def test_no_shortcuts_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            result = c.match_shortcut("run test 5")
            self.assertIsNone(result)

    def test_matching_shortcut_returned(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            template = c._extract_template("run test 42")
            c.create_shortcut(template, "run-test", "Running test")
            result = c.match_shortcut("run test 99")
            self.assertIsNotNone(result)
            self.assertEqual(result["name"], "run-test")

    def test_non_matching_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            c.create_shortcut("completely different", "other", "resp")
            result = c.match_shortcut("unrelated query")
            self.assertIsNone(result)

    def test_usage_count_incremented_on_match(self):
        with tempfile.TemporaryDirectory() as td:
            c = _chunker(td)
            template = c._extract_template("run test 1")
            c.create_shortcut(template, "rt", "resp")
            c.match_shortcut("run test 2")
            shortcuts = c.list_shortcuts()
            self.assertEqual(shortcuts[0]["usage_count"], 1)


if __name__ == "__main__":
    unittest.main()
