"""Tests for hivemind.redaction — redact_for_embedding() security function."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.redaction import redact_for_embedding


class TestRedactForEmbedding(unittest.TestCase):
    """Tests for redact_for_embedding() — credential/token redaction."""

    def test_plain_text_unchanged(self):
        text = "The routing system tracks memory attribution paths."
        self.assertEqual(redact_for_embedding(text), text)

    def test_empty_string_unchanged(self):
        self.assertEqual(redact_for_embedding(""), "")

    def test_none_returns_empty_string(self):
        result = redact_for_embedding(None)  # type: ignore
        self.assertEqual(result, "")

    def test_api_key_colon_redacted(self):
        text = "api_key: sk-abc123def456"
        result = redact_for_embedding(text)
        self.assertNotIn("sk-abc123def456", result)
        self.assertIn("[REDACTED]", result)

    def test_api_key_equals_redacted(self):
        text = "api-key=mysupersecrettoken"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("mysupersecrettoken", result)

    def test_token_field_redacted(self):
        text = "token: eyJhbGciOiJIUzI1NiJ9.payload.sig"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)

    def test_secret_field_redacted(self):
        text = "secret=AbCdEfGhIjKlMnOp1234"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)

    def test_password_field_redacted(self):
        text = "password: hunter2"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)

    def test_bearer_token_redacted(self):
        text = "authorization: bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("eyJhbGci", result)

    def test_bearer_standalone_redacted(self):
        text = "the token is Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.long"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)

    def test_hex_string_redacted(self):
        # 24+ uppercase hex chars → [REDACTED_HEX]
        text = "fingerprint: DEADBEEFCAFE0123456789AB"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED_HEX]", result)

    def test_short_hex_not_redacted(self):
        # Less than 24 hex chars → not redacted
        text = "id: DEADBEEF"  # only 8 chars
        result = redact_for_embedding(text)
        self.assertNotIn("[REDACTED_HEX]", result)

    def test_case_insensitive_api_key(self):
        text = "API_KEY: my-secret-value"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)

    def test_case_insensitive_bearer(self):
        text = "BEARER eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload"
        result = redact_for_embedding(text)
        self.assertIn("[REDACTED]", result)

    def test_multiple_credentials_all_redacted(self):
        text = "api_key: abc123 and token: xyz789 in the same text"
        result = redact_for_embedding(text)
        # Both should be redacted
        self.assertNotIn("abc123", result)
        self.assertNotIn("xyz789", result)

    def test_non_credential_content_preserved(self):
        text = "api_key: SECRET routing system manages consciousness attribution"
        result = redact_for_embedding(text)
        self.assertIn("routing", result)
        self.assertIn("consciousness", result)
        self.assertIn("attribution", result)

    def test_returns_string(self):
        result = redact_for_embedding("some text")
        self.assertIsInstance(result, str)

    def test_key_name_preserved_in_redaction(self):
        # The replacement keeps the key name: \1=[REDACTED]
        text = "api_key=secret123"
        result = redact_for_embedding(text)
        self.assertIn("api_key", result)


if __name__ == "__main__":
    unittest.main()
