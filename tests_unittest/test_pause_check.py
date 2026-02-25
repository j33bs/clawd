import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "workspace" / "memory"
if str(MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(MEMORY_DIR))

from pause_check import pause_check  # noqa: E402


class TestPauseCheck(unittest.TestCase):
    def test_pause_check_disabled_by_default(self):
        old = os.environ.pop("OPENCLAW_PAUSE_CHECK", None)
        try:
            out = pause_check("ok", "Great question. Let's dive in with some broad context.", context={"test_mode": True})
            self.assertFalse(out["enabled"])
            self.assertEqual(out["decision"], "proceed")
        finally:
            if old is not None:
                os.environ["OPENCLAW_PAUSE_CHECK"] = old

    def test_pause_check_silences_verbose_filler_when_enabled(self):
        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        try:
            draft = (
                "Great question. Let's dive in. Generally speaking, it depends and there are many things to consider. "
                "In summary, this is broad and not specific. " * 4
            )
            out = pause_check("ok", draft, context={"test_mode": True})
            self.assertTrue(out["enabled"])
            self.assertEqual(out["decision"], "silence")
            self.assertGreaterEqual(out["signals"]["fills_space"], 0.45)
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)

    def test_pause_check_proceeds_on_concrete_draft(self):
        os.environ["OPENCLAW_PAUSE_CHECK"] = "1"
        try:
            draft = "Run: python3 -m pytest tests_unittest/test_pause_check.py and inspect workspace/scripts/team_chat_adapters.py"
            out = pause_check("help", draft, context={"test_mode": True})
            self.assertTrue(out["enabled"])
            self.assertEqual(out["decision"], "proceed")
            self.assertGreater(out["signals"]["value_add"], 0.3)
        finally:
            os.environ.pop("OPENCLAW_PAUSE_CHECK", None)


if __name__ == "__main__":
    unittest.main()
