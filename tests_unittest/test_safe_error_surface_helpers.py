"""Tests for pure helpers in workspace/scripts/safe_error_surface.py.

Covers:
- _redact_text(value) — redacts secrets from arbitrary string values
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "safe_error_surface.py"

_spec = _ilu.spec_from_file_location("safe_error_surface_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["safe_error_surface_real"] = _mod
_spec.loader.exec_module(_mod)

_redact_text = _mod._redact_text


# ---------------------------------------------------------------------------
# _redact_text
# ---------------------------------------------------------------------------


class TestRedactText(unittest.TestCase):
    """Tests for _redact_text() — secret-pattern redaction from strings."""

    def test_plain_text_unchanged(self):
        self.assertEqual(_redact_text("hello world"), "hello world")

    def test_none_returns_empty_string(self):
        self.assertEqual(_redact_text(None), "")

    def test_returns_string_type(self):
        self.assertIsInstance(_redact_text("text"), str)

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
        result = _redact_text(text)
        self.assertNotIn("eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9", result)

    def test_sk_token_redacted(self):
        text = "key is sk-abcdefghij1234 in use"
        result = _redact_text(text)
        self.assertNotIn("sk-abcdefghij1234", result)
        self.assertIn("<redacted", result)

    def test_gsk_token_redacted(self):
        text = "token=gsk-1234567890abcd"
        result = _redact_text(text)
        self.assertNotIn("gsk-1234567890abcd", result)

    def test_xoxb_slack_token_redacted(self):
        text = "using xoxb-abcdef1234567890"
        result = _redact_text(text)
        self.assertNotIn("xoxb-abcdef1234567890", result)

    def test_xoxp_slack_token_redacted(self):
        text = "token xoxp-1234567890abcdefgh"
        result = _redact_text(text)
        self.assertNotIn("xoxp-1234567890abcdefgh", result)

    def test_api_key_value_redacted(self):
        text = "api_key=mysecretvalue123"
        result = _redact_text(text)
        self.assertNotIn("mysecretvalue123", result)
        self.assertIn("<redacted>", result)

    def test_token_equals_redacted(self):
        text = "token=abc123def456"
        result = _redact_text(text)
        self.assertNotIn("abc123def456", result)

    def test_secret_equals_redacted(self):
        text = "secret=my_super_secret"
        result = _redact_text(text)
        self.assertNotIn("my_super_secret", result)

    def test_password_equals_redacted(self):
        text = "password=correct_horse_battery"
        result = _redact_text(text)
        self.assertNotIn("correct_horse_battery", result)

    def test_cookie_header_redacted(self):
        text = "Cookie: session_id=abc123; user=me"
        result = _redact_text(text)
        self.assertIn("<redacted>", result)
        # "Cookie: " prefix preserved
        self.assertIn("Cookie:", result)

    def test_set_cookie_header_redacted(self):
        text = "Set-Cookie: auth=token123; Path=/"
        result = _redact_text(text)
        self.assertIn("<redacted>", result)


if __name__ == "__main__":
    unittest.main()
