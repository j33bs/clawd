import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from intent_failure_scan import redact


class TestSafeErrorSurfaceNegative(unittest.TestCase):
    def test_benign_diagnostic_not_over_redacted(self):
        message = "timeout after 30 seconds while polling status endpoint"
        self.assertEqual(redact(message), message)


if __name__ == "__main__":
    unittest.main()
