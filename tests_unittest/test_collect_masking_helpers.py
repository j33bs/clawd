"""Tests for pure helpers in workspace/scripts/collect_masking_round3.py.

Stubs requests (optional dep) to allow clean module load.
Covers (no network, no file I/O):
- int_to_roman
- format_section
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# Stub requests before loading
sys.modules.setdefault("requests", types.ModuleType("requests"))

_spec = _ilu.spec_from_file_location(
    "collect_masking_real",
    str(SCRIPTS_DIR / "collect_masking_round3.py"),
)
cm = _ilu.module_from_spec(_spec)
sys.modules["collect_masking_real"] = cm
_spec.loader.exec_module(cm)

int_to_roman = cm.int_to_roman
format_section = cm.format_section


# ---------------------------------------------------------------------------
# int_to_roman
# ---------------------------------------------------------------------------

class TestIntToRoman(unittest.TestCase):
    """Tests for int_to_roman() — integer to Roman numeral string."""

    def test_one(self):
        self.assertEqual(int_to_roman(1), "I")

    def test_four(self):
        self.assertEqual(int_to_roman(4), "IV")

    def test_nine(self):
        self.assertEqual(int_to_roman(9), "IX")

    def test_forty(self):
        self.assertEqual(int_to_roman(40), "XL")

    def test_ninety(self):
        self.assertEqual(int_to_roman(90), "XC")

    def test_hundred(self):
        self.assertEqual(int_to_roman(100), "C")

    def test_four_hundred(self):
        self.assertEqual(int_to_roman(400), "CD")

    def test_five_hundred(self):
        self.assertEqual(int_to_roman(500), "D")

    def test_nine_hundred(self):
        self.assertEqual(int_to_roman(900), "CM")

    def test_thousand(self):
        self.assertEqual(int_to_roman(1000), "M")

    def test_three(self):
        self.assertEqual(int_to_roman(3), "III")

    def test_fourteen(self):
        self.assertEqual(int_to_roman(14), "XIV")

    def test_forty_two(self):
        self.assertEqual(int_to_roman(42), "XLII")

    def test_1984(self):
        self.assertEqual(int_to_roman(1984), "MCMLXXXIV")

    def test_2026(self):
        self.assertEqual(int_to_roman(2026), "MMXXVI")

    def test_returns_string(self):
        self.assertIsInstance(int_to_roman(5), str)

    def test_149(self):
        self.assertEqual(int_to_roman(149), "CXLIX")

    def test_158(self):
        self.assertEqual(int_to_roman(158), "CLVIII")


# ---------------------------------------------------------------------------
# format_section
# ---------------------------------------------------------------------------

class TestFormatSection(unittest.TestCase):
    """Tests for format_section() — format a section entry for OPEN_QUESTIONS.md."""

    def test_contains_roman_numeral(self):
        result = format_section("CLXI", "TestBeing", "Some content.")
        self.assertIn("CLXI", result)

    def test_contains_being_name(self):
        result = format_section("CLXI", "TestBeing", "Some content.")
        self.assertIn("TestBeing", result)

    def test_contains_content(self):
        result = format_section("CLXI", "TestBeing", "Some content.")
        self.assertIn("Some content.", result)

    def test_contains_masking_variant(self):
        result = format_section("CLXI", "TestBeing", "Content.")
        self.assertIn("[MASKING_VARIANT]", result)

    def test_contains_separator(self):
        result = format_section("CLXI", "TestBeing", "Content.")
        self.assertIn("---", result)

    def test_custom_round_num(self):
        result = format_section("CLXI", "TestBeing", "Content.", round_num=4)
        self.assertIn("Round 4", result)

    def test_default_round_num_3(self):
        result = format_section("CLXI", "TestBeing", "Content.")
        self.assertIn("Round 3", result)

    def test_returns_string(self):
        result = format_section("I", "Being", "Content.")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
