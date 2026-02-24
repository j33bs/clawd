import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from intent_failure_scan import redact
from safe_error_surface import create_safe_error_envelope


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
