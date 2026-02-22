import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

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


if __name__ == "__main__":
    unittest.main()
