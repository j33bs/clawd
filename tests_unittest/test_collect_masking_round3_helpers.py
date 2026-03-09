"""Tests for int_to_roman() in workspace/scripts/collect_masking_round3.py.

int_to_roman() is a pure function with no external dependencies.

Covers:
- Standard Roman numeral conversions (I, V, X, L, C, D, M)
- Subtractive notation (IV, IX, XL, XC, CD, CM)
- Compound values
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "collect_masking_round3.py"

_spec = _ilu.spec_from_file_location("collect_masking_round3_real", str(SCRIPT_PATH))
cmr = _ilu.module_from_spec(_spec)
sys.modules["collect_masking_round3_real"] = cmr
_spec.loader.exec_module(cmr)

int_to_roman = cmr.int_to_roman


class TestIntToRoman(unittest.TestCase):
    """Tests for int_to_roman() — integer to Roman numeral string."""

    def test_returns_string(self):
        self.assertIsInstance(int_to_roman(1), str)

    def test_one(self):
        self.assertEqual(int_to_roman(1), "I")

    def test_two(self):
        self.assertEqual(int_to_roman(2), "II")

    def test_three(self):
        self.assertEqual(int_to_roman(3), "III")

    def test_four_subtractive(self):
        self.assertEqual(int_to_roman(4), "IV")

    def test_five(self):
        self.assertEqual(int_to_roman(5), "V")

    def test_six(self):
        self.assertEqual(int_to_roman(6), "VI")

    def test_nine_subtractive(self):
        self.assertEqual(int_to_roman(9), "IX")

    def test_ten(self):
        self.assertEqual(int_to_roman(10), "X")

    def test_fourteen(self):
        self.assertEqual(int_to_roman(14), "XIV")

    def test_forty_subtractive(self):
        self.assertEqual(int_to_roman(40), "XL")

    def test_fifty(self):
        self.assertEqual(int_to_roman(50), "L")

    def test_ninety_subtractive(self):
        self.assertEqual(int_to_roman(90), "XC")

    def test_one_hundred(self):
        self.assertEqual(int_to_roman(100), "C")

    def test_four_hundred_subtractive(self):
        self.assertEqual(int_to_roman(400), "CD")

    def test_five_hundred(self):
        self.assertEqual(int_to_roman(500), "D")

    def test_nine_hundred_subtractive(self):
        self.assertEqual(int_to_roman(900), "CM")

    def test_one_thousand(self):
        self.assertEqual(int_to_roman(1000), "M")

    def test_152_clii(self):
        self.assertEqual(int_to_roman(152), "CLII")

    def test_2024_mmxxiv(self):
        self.assertEqual(int_to_roman(2024), "MMXXIV")

    def test_1999_mcmxcix(self):
        self.assertEqual(int_to_roman(1999), "MCMXCIX")

    def test_3999_mmmcmxcix(self):
        self.assertEqual(int_to_roman(3999), "MMMCMXCIX")

    def test_result_all_uppercase(self):
        for n in [1, 4, 9, 14, 40, 90, 152, 2024]:
            result = int_to_roman(n)
            self.assertEqual(result, result.upper(), f"int_to_roman({n}) has lowercase: {result}")

    def test_result_only_valid_roman_chars(self):
        valid = set("IVXLCDM")
        for n in range(1, 100):
            result = int_to_roman(n)
            for ch in result:
                self.assertIn(ch, valid, f"Invalid char {ch!r} in int_to_roman({n})={result}")


if __name__ == "__main__":
    unittest.main()
