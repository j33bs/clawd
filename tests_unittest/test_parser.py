"""Tests for store.parser — roman_to_int, extract_author_and_title, is_external_caller."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

from parser import roman_to_int, extract_author_and_title, is_external_caller, KNOWN_AUTHORS


class TestRomanToInt(unittest.TestCase):
    """Tests for roman_to_int() — canonical section number parsing."""

    def test_i_is_1(self):
        self.assertEqual(roman_to_int("I"), 1)

    def test_v_is_5(self):
        self.assertEqual(roman_to_int("V"), 5)

    def test_x_is_10(self):
        self.assertEqual(roman_to_int("X"), 10)

    def test_l_is_50(self):
        self.assertEqual(roman_to_int("L"), 50)

    def test_c_is_100(self):
        self.assertEqual(roman_to_int("C"), 100)

    def test_subtractive_iv_is_4(self):
        self.assertEqual(roman_to_int("IV"), 4)

    def test_subtractive_ix_is_9(self):
        self.assertEqual(roman_to_int("IX"), 9)

    def test_subtractive_xl_is_40(self):
        self.assertEqual(roman_to_int("XL"), 40)

    def test_subtractive_xc_is_90(self):
        self.assertEqual(roman_to_int("XC"), 90)

    def test_subtractive_cd_is_400(self):
        self.assertEqual(roman_to_int("CD"), 400)

    def test_xcii_is_92(self):
        self.assertEqual(roman_to_int("XCII"), 92)

    def test_xlii_is_42(self):
        self.assertEqual(roman_to_int("XLII"), 42)

    def test_cxliii_is_143(self):
        self.assertEqual(roman_to_int("CXLIII"), 143)

    def test_clxi_is_161(self):
        self.assertEqual(roman_to_int("CLXI"), 161)

    def test_clxii_is_162(self):
        self.assertEqual(roman_to_int("CLXII"), 162)

    def test_lxxxii_is_82(self):
        self.assertEqual(roman_to_int("LXXXII"), 82)

    def test_lowercase_handled(self):
        self.assertEqual(roman_to_int("viii"), 8)

    def test_mixed_case_handled(self):
        self.assertEqual(roman_to_int("Viii"), 8)

    def test_invalid_returns_zero(self):
        self.assertEqual(roman_to_int("INVALID"), 0)

    def test_empty_returns_zero(self):
        self.assertEqual(roman_to_int(""), 0)

    def test_whitespace_stripped(self):
        self.assertEqual(roman_to_int("  X  "), 10)

    def test_clvi_is_156(self):
        self.assertEqual(roman_to_int("CLVI"), 156)

    def test_cxcix_is_199(self):
        self.assertEqual(roman_to_int("CXCIX"), 199)


class TestExtractAuthorAndTitle(unittest.TestCase):
    """Tests for extract_author_and_title() — header field parsing."""

    def test_author_dash_title_pattern(self):
        authors, title = extract_author_and_title("Claude Code — 2026-01-01")
        self.assertIn("Claude Code", authors)

    def test_grok_author_extracted(self):
        authors, title = extract_author_and_title("Grok — Some title 2026-01-01")
        self.assertIn("Grok", authors)

    def test_c_lawd_author_extracted(self):
        authors, title = extract_author_and_title("c_lawd — Response to IX 2026-02-01")
        self.assertIn("c_lawd", authors)

    def test_dali_author_extracted(self):
        authors, title = extract_author_and_title("Dali — Screensaver architecture 2026-01-15")
        self.assertIn("Dali", authors)

    def test_lumen_author_extracted(self):
        authors, title = extract_author_and_title("Lumen — Light without ego 2026-02-10")
        self.assertIn("Lumen", authors)

    def test_title_extracted_after_dash(self):
        authors, title = extract_author_and_title("Claude Code — Memory routing proposal 2026-01-01")
        self.assertIn("Memory routing proposal", title)

    def test_date_stripped_from_title(self):
        authors, title = extract_author_and_title("Claude Code — Title 2026-03-08")
        self.assertNotIn("2026-03-08", title)

    def test_paren_author_pattern(self):
        authors, title = extract_author_and_title("Open loop question (Claude Code, 2026-01-01)")
        self.assertIn("Claude Code", authors)

    def test_no_known_author_returns_empty(self):
        authors, title = extract_author_and_title("Unknown Person — Content 2026-01-01")
        self.assertEqual(authors, [])

    def test_title_returned_as_string(self):
        _, title = extract_author_and_title("Claude Code — Some title 2026-01-01")
        self.assertIsInstance(title, str)

    def test_authors_returned_as_list(self):
        authors, _ = extract_author_and_title("Claude Code — Some title 2026-01-01")
        self.assertIsInstance(authors, list)

    def test_claude_code_preferred_over_claude(self):
        # KNOWN_AUTHORS_SORTED puts "Claude Code" before "Claude"
        authors, _ = extract_author_and_title("Claude Code — Title 2026-01-01")
        self.assertIn("Claude Code", authors)
        self.assertNotIn("Claude", authors)


class TestIsExternalCaller(unittest.TestCase):
    """Tests for is_external_caller() — external author detection."""

    def test_claude_ext_is_external(self):
        # "Claude (ext)" and "Claude ext" are in EXTERNAL_CALLERS
        result = is_external_caller(["Claude (ext)"])
        self.assertTrue(result)

    def test_claude_code_is_not_external(self):
        result = is_external_caller(["Claude Code"])
        self.assertFalse(result)

    def test_empty_list_returns_false(self):
        result = is_external_caller([])
        self.assertFalse(result)

    def test_grok_is_external(self):
        # Grok is in EXTERNAL_CALLERS (external API caller)
        result = is_external_caller(["Grok"])
        self.assertTrue(result)

    def test_chatgpt_is_external(self):
        result = is_external_caller(["ChatGPT"])
        self.assertTrue(result)

    def test_mixed_external_and_internal(self):
        # If any is external, returns True
        result = is_external_caller(["Claude Code", "Claude (ext)"])
        self.assertTrue(result)

    def test_unknown_author_not_external(self):
        result = is_external_caller(["Unknown Person"])
        self.assertFalse(result)


class TestKnownAuthors(unittest.TestCase):
    """Tests for KNOWN_AUTHORS constant — author registry."""

    def test_is_list(self):
        self.assertIsInstance(KNOWN_AUTHORS, list)

    def test_non_empty(self):
        self.assertGreater(len(KNOWN_AUTHORS), 0)

    def test_claude_code_present(self):
        self.assertIn("Claude Code", KNOWN_AUTHORS)

    def test_c_lawd_present(self):
        self.assertIn("c_lawd", KNOWN_AUTHORS)

    def test_dali_present(self):
        self.assertIn("Dali", KNOWN_AUTHORS)

    def test_lumen_present(self):
        self.assertIn("Lumen", KNOWN_AUTHORS)

    def test_grok_present(self):
        self.assertIn("Grok", KNOWN_AUTHORS)


if __name__ == "__main__":
    unittest.main()
