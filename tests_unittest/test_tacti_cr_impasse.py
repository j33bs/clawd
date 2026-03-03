import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti.impasse import ImpasseManager  # noqa: E402


class TestImpasseManager(unittest.TestCase):
    def test_first_failure_enters_impasse_not_collapse(self):
        manager = ImpasseManager(collapse_after=3, clear_after_stable=2)
        snapshot = manager.on_failure("tool timeout")
        self.assertEqual("impasse", snapshot["status"])
        self.assertEqual(1, snapshot["consecutive_failures"])
        self.assertFalse(snapshot["repairable"])
        self.assertTrue(snapshot["optional_modules_enabled"])

    def test_repeated_failures_trigger_repairable_collapse(self):
        manager = ImpasseManager(collapse_after=3, clear_after_stable=2)
        manager.on_failure("tool timeout")
        manager.on_failure("tool timeout")
        snapshot = manager.on_failure("tool timeout")
        self.assertEqual("collapse", snapshot["status"])
        self.assertTrue(snapshot["repairable"])
        self.assertFalse(snapshot["optional_modules_enabled"])
        self.assertTrue(snapshot["force_compaction"])
        self.assertEqual(2, snapshot["retrieval_limit"])

    def test_stable_success_recovers_from_collapse(self):
        manager = ImpasseManager(collapse_after=2, clear_after_stable=2)
        manager.on_failure("provider error")
        manager.on_failure("provider error")
        self.assertEqual("collapse", manager.on_failure("context overflow", context_overflow=True)["status"])
        self.assertEqual("collapse", manager.on_success()["status"])
        recovered = manager.on_success()
        self.assertEqual("healthy", recovered["status"])
        self.assertEqual(0, recovered["consecutive_failures"])

    def test_legacy_shim_import_still_resolves(self):
        from tacti_cr.impasse import ImpasseManager as LegacyImpasseManager

        self.assertIsNotNone(LegacyImpasseManager)


if __name__ == "__main__":
    unittest.main()
