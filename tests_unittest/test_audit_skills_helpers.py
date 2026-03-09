"""Tests for pure helpers in workspace/scripts/audit_skills.py.

Covers:
- _is_private_ip(host) — private IP range detection
- _to_line_number(text, offset) — byte offset → 1-based line number
- _snippet(text, start, end, max_len=220) — safe text snippet extractor
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "audit_skills.py"

_spec = _ilu.spec_from_file_location("audit_skills_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["audit_skills_real"] = _mod
_spec.loader.exec_module(_mod)

_is_private_ip = _mod._is_private_ip
_to_line_number = _mod._to_line_number
_snippet = _mod._snippet


# ---------------------------------------------------------------------------
# _is_private_ip
# ---------------------------------------------------------------------------


class TestIsPrivateIp(unittest.TestCase):
    """Tests for _is_private_ip() — private RFC-1918 / loopback detection."""

    def test_empty_string_false(self):
        self.assertFalse(_is_private_ip(""))

    def test_10_x_x_x_is_private(self):
        self.assertTrue(_is_private_ip("10.0.0.1"))
        self.assertTrue(_is_private_ip("10.255.255.255"))

    def test_127_x_x_x_is_private(self):
        self.assertTrue(_is_private_ip("127.0.0.1"))
        self.assertTrue(_is_private_ip("127.255.255.255"))

    def test_192_168_is_private(self):
        self.assertTrue(_is_private_ip("192.168.1.1"))
        self.assertTrue(_is_private_ip("192.168.0.0"))

    def test_192_169_not_private(self):
        self.assertFalse(_is_private_ip("192.169.0.1"))

    def test_172_16_to_31_is_private(self):
        self.assertTrue(_is_private_ip("172.16.0.0"))
        self.assertTrue(_is_private_ip("172.31.255.255"))
        self.assertTrue(_is_private_ip("172.20.5.1"))

    def test_172_15_not_private(self):
        self.assertFalse(_is_private_ip("172.15.0.1"))

    def test_172_32_not_private(self):
        self.assertFalse(_is_private_ip("172.32.0.1"))

    def test_public_ip_false(self):
        self.assertFalse(_is_private_ip("8.8.8.8"))
        self.assertFalse(_is_private_ip("93.184.216.34"))

    def test_hostname_false(self):
        self.assertFalse(_is_private_ip("localhost"))
        self.assertFalse(_is_private_ip("example.com"))

    def test_too_few_octets_false(self):
        self.assertFalse(_is_private_ip("10.0.1"))

    def test_non_numeric_octets_false(self):
        self.assertFalse(_is_private_ip("10.x.0.1"))

    def test_returns_bool(self):
        self.assertIsInstance(_is_private_ip("10.0.0.1"), bool)


# ---------------------------------------------------------------------------
# _to_line_number
# ---------------------------------------------------------------------------


class TestToLineNumber(unittest.TestCase):
    """Tests for _to_line_number() — offset to 1-based line number."""

    def test_offset_zero_is_line_1(self):
        self.assertEqual(_to_line_number("hello\nworld", 0), 1)

    def test_no_newlines_always_line_1(self):
        self.assertEqual(_to_line_number("hello world", 5), 1)

    def test_after_first_newline_is_line_2(self):
        # "abc\n" — offset 4 (after newline) → line 2
        self.assertEqual(_to_line_number("abc\nxyz", 4), 2)

    def test_empty_string_offset_0_is_line_1(self):
        self.assertEqual(_to_line_number("", 0), 1)

    def test_two_newlines_offset_at_third_line(self):
        text = "a\nb\nc"
        self.assertEqual(_to_line_number(text, text.index("c")), 3)

    def test_negative_offset_treated_as_zero(self):
        # max(0, -1) → 0 → line 1
        self.assertEqual(_to_line_number("hello\nworld", -1), 1)

    def test_returns_int(self):
        self.assertIsInstance(_to_line_number("hello", 0), int)


# ---------------------------------------------------------------------------
# _snippet
# ---------------------------------------------------------------------------


class TestSnippet(unittest.TestCase):
    """Tests for _snippet() — safe text snippet with truncation."""

    def test_short_snippet_unchanged(self):
        text = "hello world"
        result = _snippet(text, 0, len(text))
        self.assertEqual(result, "hello world")

    def test_newlines_replaced_with_spaces(self):
        result = _snippet("hello\nworld", 0, 11)
        self.assertNotIn("\n", result)
        self.assertIn(" ", result)

    def test_leading_trailing_whitespace_stripped(self):
        result = _snippet("  hello  ", 0, 9)
        self.assertEqual(result, "hello")

    def test_long_snippet_truncated(self):
        text = "x" * 300
        result = _snippet(text, 0, 300)
        self.assertTrue(result.endswith("..."))

    def test_truncated_at_max_len(self):
        text = "a" * 300
        result = _snippet(text, 0, 300, max_len=100)
        self.assertEqual(result, "a" * 97 + "...")

    def test_custom_max_len_exact(self):
        text = "b" * 50
        result = _snippet(text, 0, 50, max_len=50)
        self.assertEqual(result, "b" * 50)

    def test_slice_respected(self):
        text = "hello world test"
        result = _snippet(text, 6, 11)  # "world"
        self.assertEqual(result, "world")

    def test_empty_slice_returns_empty(self):
        result = _snippet("hello", 2, 2)
        self.assertEqual(result, "")

    def test_returns_string(self):
        self.assertIsInstance(_snippet("text", 0, 4), str)


if __name__ == "__main__":
    unittest.main()
