import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.repair import RepairEngine  # noqa: E402


class TestTactiCRRepair(unittest.TestCase):
    def setUp(self):
        self.engine = RepairEngine()

    def test_can_recover_for_transient_errors(self):
        self.assertTrue(self.engine.can_recover("timeout during dispatch"))
        self.assertTrue(self.engine.can_recover("connection refused upstream"))
        self.assertFalse(self.engine.can_recover("invalid prompt format"))

    def test_timeout_maps_to_retry_backoff(self):
        action = self.engine.repair("operation aborted due to timeout")
        self.assertEqual(action.action, "retry_with_backoff")
        self.assertTrue(action.retryable)

    def test_auth_maps_to_operator_refresh(self):
        action = self.engine.repair("provider returned 401 unauthorized")
        self.assertEqual(action.action, "request_operator_auth_refresh")
        self.assertFalse(action.retryable)

    def test_unknown_maps_to_safe_reset(self):
        action = self.engine.repair("unexpected parse issue")
        self.assertEqual(action.action, "safe_reset")
        self.assertFalse(action.retryable)


if __name__ == "__main__":
    unittest.main()
