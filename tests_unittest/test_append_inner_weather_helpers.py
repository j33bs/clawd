"""Tests for pure helpers in workspace/scripts/append_inner_weather.py.

Covers:
- _sanitize(note) — redacts emails and long tokens, normalises whitespace
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "append_inner_weather.py"

_spec = _ilu.spec_from_file_location("append_inner_weather_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["append_inner_weather_real"] = _mod
_spec.loader.exec_module(_mod)

_sanitize = _mod._sanitize


# ---------------------------------------------------------------------------
# _sanitize
# ---------------------------------------------------------------------------


class TestSanitize(unittest.TestCase):
    """Tests for _sanitize() — email + long-token redaction with whitespace norm."""

    def test_plain_text_unchanged(self):
        self.assertEqual(_sanitize("hello world"), "hello world")

    def test_email_redacted(self):
        result = _sanitize("contact user@example.com please")
        self.assertNotIn("user@example.com", result)
        self.assertIn("[REDACTED_EMAIL]", result)

    def test_multiple_emails_all_redacted(self):
        result = _sanitize("a@b.com and c@d.org are redacted")
        self.assertEqual(result.count("[REDACTED_EMAIL]"), 2)

    def test_long_token_redacted(self):
        # 24-char token
        token = "A" * 24
        result = _sanitize(f"token is {token} here")
        self.assertNotIn(token, result)
        self.assertIn("[REDACTED_TOKEN]", result)

    def test_short_token_not_redacted(self):
        # 23 chars — below threshold
        short = "B" * 23
        result = _sanitize(f"id is {short} here")
        self.assertIn(short, result)

    def test_exactly_24_chars_redacted(self):
        token = "C" * 24
        result = _sanitize(token)
        self.assertIn("[REDACTED_TOKEN]", result)

    def test_multiple_whitespace_normalised(self):
        result = _sanitize("hello   world\t foo")
        self.assertEqual(result, "hello world foo")

    def test_leading_trailing_whitespace_stripped(self):
        result = _sanitize("  hello world  ")
        self.assertEqual(result, "hello world")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_sanitize(""), "")

    def test_returns_string(self):
        self.assertIsInstance(_sanitize("text"), str)

    def test_email_and_token_both_redacted(self):
        token = "D" * 30
        result = _sanitize(f"key={token} email=me@host.io")
        self.assertIn("[REDACTED_TOKEN]", result)
        self.assertIn("[REDACTED_EMAIL]", result)


if __name__ == "__main__":
    unittest.main()
