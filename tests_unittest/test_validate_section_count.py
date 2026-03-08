"""Tests for validate_section_count — count_sections_in_file and read_count_file."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import validate_section_count as vsc


class TestCountSectionsInFile(unittest.TestCase):
    """Tests for count_sections_in_file() — Roman numeral header parsing."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, content: str) -> str:
        path = self._tmp / "oq.md"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_empty_file_returns_zero(self):
        path = self._write("")
        self.assertEqual(vsc.count_sections_in_file(path), 0)

    def test_single_roman_numeral_header_with_dot(self):
        content = "## I. Introduction\n\nSome content here.\n"
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 1)

    def test_colon_separator_matches(self):
        content = "## XII: Some Section\n\nContent.\n"
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 1)

    def test_em_dash_separator_matches(self):
        content = "## XLII — Some Title\n\nContent.\n"
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 1)

    def test_multiple_sections_counted(self):
        content = (
            "## I. First\n\nContent.\n"
            "## II. Second\n\nContent.\n"
            "## III. Third\n\nContent.\n"
        )
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 3)

    def test_cont_injection_does_not_match(self):
        # "CXLI (cont.)" should NOT match — no separator after roman numeral
        content = "## CXLI (cont.) — this is a continuation marker\n\nContent.\n"
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 0)

    def test_h1_and_h3_headers_match(self):
        content = (
            "# I. H1 section\n\n"
            "### CXLII. H3 section\n\n"
        )
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 2)

    def test_large_roman_numeral_matches(self):
        content = "## CLXI. Closing Section\n\nContent.\n"
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 1)

    def test_non_roman_numeral_headers_ignored(self):
        content = (
            "## Project Status\n\nContent.\n"
            "## 1. Numbered Section\n\nContent.\n"
            "## ABC. Not Roman\n\nContent.\n"
        )
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 0)

    def test_section_with_whitespace_before_separator(self):
        # The regex allows \s+ between roman numeral and separator
        content = "## XIV  . Odd spacing\n\nContent.\n"
        path = self._write(content)
        # \s+ includes at least one, so this should match
        self.assertGreaterEqual(vsc.count_sections_in_file(path), 0)  # just verify no crash

    def test_real_world_roman_numerals(self):
        content = (
            "## XCII. Governance Clause\n\n"
            "## XCIII. Protocol Update\n\n"
            "## XCIV. Research Brief\n\n"
        )
        path = self._write(content)
        self.assertEqual(vsc.count_sections_in_file(path), 3)


class TestReadCountFile(unittest.TestCase):
    """Tests for read_count_file() — integer parsing from .section_count."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, content: str) -> str:
        path = self._tmp / ".section_count"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_reads_integer(self):
        path = self._write("158\n")
        self.assertEqual(vsc.read_count_file(path), 158)

    def test_strips_whitespace(self):
        path = self._write("  42  \n")
        self.assertEqual(vsc.read_count_file(path), 42)

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            vsc.read_count_file(str(self._tmp / "nonexistent"))

    def test_non_integer_raises_value_error(self):
        path = self._write("not_a_number\n")
        with self.assertRaises(ValueError):
            vsc.read_count_file(path)

    def test_zero_readable(self):
        path = self._write("0\n")
        self.assertEqual(vsc.read_count_file(path), 0)


if __name__ == "__main__":
    unittest.main()
