"""Tests for store.orient — int_to_roman, read_count, write_count, count_actual_sections."""
import sys
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

import orient


class TestIntToRoman(unittest.TestCase):
    """Tests for int_to_roman() — integer → Roman numeral conversion."""

    def test_1_is_I(self):
        self.assertEqual(orient.int_to_roman(1), "I")

    def test_4_is_IV(self):
        self.assertEqual(orient.int_to_roman(4), "IV")

    def test_5_is_V(self):
        self.assertEqual(orient.int_to_roman(5), "V")

    def test_9_is_IX(self):
        self.assertEqual(orient.int_to_roman(9), "IX")

    def test_10_is_X(self):
        self.assertEqual(orient.int_to_roman(10), "X")

    def test_14_is_XIV(self):
        self.assertEqual(orient.int_to_roman(14), "XIV")

    def test_40_is_XL(self):
        self.assertEqual(orient.int_to_roman(40), "XL")

    def test_50_is_L(self):
        self.assertEqual(orient.int_to_roman(50), "L")

    def test_90_is_XC(self):
        self.assertEqual(orient.int_to_roman(90), "XC")

    def test_99_is_XCIX(self):
        self.assertEqual(orient.int_to_roman(99), "XCIX")

    def test_100_is_C(self):
        self.assertEqual(orient.int_to_roman(100), "C")

    def test_158_is_CLVIII(self):
        # Current corpus size
        self.assertEqual(orient.int_to_roman(158), "CLVIII")

    def test_161_is_CLXI(self):
        self.assertEqual(orient.int_to_roman(161), "CLXI")

    def test_400_is_CD(self):
        self.assertEqual(orient.int_to_roman(400), "CD")

    def test_500_is_D(self):
        self.assertEqual(orient.int_to_roman(500), "D")

    def test_900_is_CM(self):
        self.assertEqual(orient.int_to_roman(900), "CM")

    def test_1000_is_M(self):
        self.assertEqual(orient.int_to_roman(1000), "M")

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            orient.int_to_roman(0)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            orient.int_to_roman(-1)

    def test_returns_string(self):
        self.assertIsInstance(orient.int_to_roman(5), str)

    def test_uppercase_only(self):
        result = orient.int_to_roman(42)
        self.assertEqual(result, result.upper())

    def test_roundtrip_with_roman_to_int(self):
        # Verify int_to_roman is the inverse of roman_to_int from parser.py
        from parser import roman_to_int
        for n in [1, 4, 9, 14, 40, 50, 90, 99, 100, 158, 161, 400, 500, 900, 1000]:
            self.assertEqual(roman_to_int(orient.int_to_roman(n)), n)


class TestReadWriteCount(unittest.TestCase):
    """Tests for read_count() and write_count() — .section_count file I/O."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_count_file = orient.COUNT_FILE
        orient.COUNT_FILE = os.path.join(self._tmpdir.name, ".section_count")

    def tearDown(self):
        orient.COUNT_FILE = self._original_count_file
        self._tmpdir.cleanup()

    def test_write_then_read_roundtrip(self):
        orient.write_count(42)
        self.assertEqual(orient.read_count(), 42)

    def test_write_then_read_158(self):
        orient.write_count(158)
        self.assertEqual(orient.read_count(), 158)

    def test_write_appends_newline(self):
        orient.write_count(10)
        with open(orient.COUNT_FILE) as f:
            content = f.read()
        self.assertTrue(content.endswith("\n"))

    def test_write_count_creates_file(self):
        orient.write_count(5)
        self.assertTrue(os.path.exists(orient.COUNT_FILE))

    def test_read_missing_file_exits(self):
        # read_count() calls sys.exit(1) when file missing
        with self.assertRaises(SystemExit):
            orient.read_count()

    def test_write_count_overwrites(self):
        orient.write_count(10)
        orient.write_count(20)
        self.assertEqual(orient.read_count(), 20)


class TestCountActualSections(unittest.TestCase):
    """Tests for count_actual_sections() — Roman-numeral header counting."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_oq_path = orient.OQ_PATH
        orient.OQ_PATH = os.path.join(self._tmpdir.name, "OPEN_QUESTIONS.md")

    def tearDown(self):
        orient.OQ_PATH = self._original_oq_path
        self._tmpdir.cleanup()

    def _write_oq(self, content: str) -> None:
        with open(orient.OQ_PATH, "w", encoding="utf-8") as f:
            f.write(content)

    def test_missing_file_returns_minus_one(self):
        result = orient.count_actual_sections()
        self.assertEqual(result, -1)

    def test_empty_file_returns_zero(self):
        self._write_oq("")
        self.assertEqual(orient.count_actual_sections(), 0)

    def test_one_section_counted(self):
        self._write_oq("## I. Author — Title (2026-01-01)\n\nBody text.\n")
        self.assertEqual(orient.count_actual_sections(), 1)

    def test_three_sections_counted(self):
        content = (
            "## I. A — Title 1 (2026-01-01)\n\nBody 1.\n\n"
            "## II. B — Title 2 (2026-01-02)\n\nBody 2.\n\n"
            "## III. C — Title 3 (2026-01-03)\n\nBody 3.\n"
        )
        self._write_oq(content)
        self.assertEqual(orient.count_actual_sections(), 3)

    def test_non_roman_headers_not_counted(self):
        content = (
            "# Main Heading\n\n"
            "## 1. Numbered section\n\n"
            "## I. Valid section (2026-01-01)\n\n"
            "### Sub-heading\n"
        )
        self._write_oq(content)
        self.assertEqual(orient.count_actual_sections(), 1)

    def test_body_lines_not_counted(self):
        content = (
            "## I. Section (2026-01-01)\n\n"
            "This mentions ## II in the body but is not a header.\n"
        )
        self._write_oq(content)
        self.assertEqual(orient.count_actual_sections(), 1)

    def test_large_roman_numerals_counted(self):
        content = "## CLVIII. Author — Title (2026-03-06)\n\nBody.\n"
        self._write_oq(content)
        self.assertEqual(orient.count_actual_sections(), 1)


if __name__ == "__main__":
    unittest.main()
