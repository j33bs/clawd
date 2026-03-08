import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from intent_failure_scan import redact
from safe_error_surface import (  # noqa: E402
    create_safe_error_envelope,
    next_request_id,
    adapter_public_error,
    format_adapter_public_error,
    redact as surface_redact,
)


class TestNextRequestId(unittest.TestCase):
    """Tests for safe_error_surface.next_request_id()."""

    def test_returns_string(self):
        self.assertIsInstance(next_request_id(), str)

    def test_contains_prefix(self):
        result = next_request_id("myprefix")
        self.assertTrue(result.startswith("myprefix-"))

    def test_default_prefix_req(self):
        result = next_request_id()
        self.assertTrue(result.startswith("req-"))

    def test_unique(self):
        a = next_request_id()
        b = next_request_id()
        self.assertNotEqual(a, b)

    def test_special_chars_in_prefix_stripped(self):
        result = next_request_id("my@prefix!")
        self.assertTrue(result.startswith("myprefix-"))


class TestSurfaceRedact(unittest.TestCase):
    """Tests for safe_error_surface.redact() — recursive redaction."""

    def test_none_passthrough(self):
        self.assertIsNone(surface_redact(None))

    def test_plain_string_no_secret_unchanged(self):
        self.assertEqual(surface_redact("timeout after 30s"), "timeout after 30s")

    def test_api_key_in_string_redacted(self):
        result = surface_redact("Bearer sk-abc123secret")
        self.assertNotIn("sk-abc123secret", result)

    def test_dict_secret_key_redacted(self):
        result = surface_redact({"api_key": "sk-secret", "model": "gpt-4"})
        self.assertEqual(result["api_key"], "<redacted>")
        self.assertEqual(result["model"], "gpt-4")

    def test_list_items_recursed(self):
        result = surface_redact(["safe", "also safe"])
        self.assertIn("safe", result)

    def test_integer_passthrough(self):
        self.assertEqual(surface_redact(42), 42)


class TestAdapterPublicError(unittest.TestCase):
    """Tests for safe_error_surface.adapter_public_error()."""

    def _envelope(self, **kwargs):
        base = {"public_message": "error", "error_code": "test_code", "request_id": "req-1"}
        base.update(kwargs)
        return base

    def test_returns_dict(self):
        self.assertIsInstance(adapter_public_error(self._envelope()), dict)

    def test_contains_public_message(self):
        result = adapter_public_error(self._envelope(public_message="oops"))
        self.assertEqual(result["public_message"], "oops")

    def test_contains_error_code(self):
        result = adapter_public_error(self._envelope(error_code="my_code"))
        self.assertEqual(result["error_code"], "my_code")

    def test_contains_request_id(self):
        result = adapter_public_error(self._envelope(request_id="req-42"))
        self.assertEqual(result["request_id"], "req-42")

    def test_missing_request_id_auto_generated(self):
        result = adapter_public_error({"public_message": "err", "error_code": "x"})
        self.assertIsNotNone(result["request_id"])

    def test_extra_keys_not_in_output(self):
        result = adapter_public_error(self._envelope(secret_key="bad"))
        self.assertNotIn("secret_key", result)


class TestFormatAdapterPublicError(unittest.TestCase):
    """Tests for safe_error_surface.format_adapter_public_error()."""

    def _env(self):
        return {"public_message": "oops", "error_code": "test_code", "request_id": "req-1"}

    def test_returns_string(self):
        self.assertIsInstance(format_adapter_public_error(self._env()), str)

    def test_contains_public_message(self):
        result = format_adapter_public_error(self._env())
        self.assertIn("oops", result)

    def test_contains_error_code(self):
        result = format_adapter_public_error(self._env())
        self.assertIn("test_code", result)

    def test_contains_request_id(self):
        result = format_adapter_public_error(self._env())
        self.assertIn("req-1", result)


class TestSafeErrorSurface(unittest.TestCase):
    def test_envelope_redacts_malicious_public_message(self):
        envelope = create_safe_error_envelope(
            public_message="Authorization: Bearer sk-abc123secret",
            error_code="tg-timeout",
            request_id="req-test",
        )
        public_message = envelope["public_message"]
        self.assertNotIn("sk-abc123secret", public_message)
        self.assertIn("<redacted>", public_message)

    def test_benign_diagnostic_not_over_redacted(self):
        message = "timeout after 30 seconds while polling status endpoint"
        self.assertEqual(redact(message), message)


if __name__ == "__main__":
    unittest.main()
