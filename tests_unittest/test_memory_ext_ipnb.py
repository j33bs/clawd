import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext import ipnb_practices


class TestMemoryExtIPNB(unittest.TestCase):
    def test_off_by_default_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                result = ipnb_practices.somatic_checkin()
                self.assertFalse(result["enabled"])
                target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "somatic_log.md"
                self.assertFalse(target.exists())

    def test_enabled_writes_and_recall(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                now = datetime(2026, 2, 25, 12, 0, tzinfo=timezone.utc)
                out = ipnb_practices.somatic_checkin(now=now)
                self.assertTrue(out["enabled"])
                recall = ipnb_practices.temporal_recall("all")
                self.assertGreaterEqual(len(recall["memory_entries"]), 1)
                self.assertIn("somatic_checkin", recall["themes"])
                rel = ipnb_practices.mwe_activator("we should co regulate together")
                self.assertEqual(rel["mode"], "co_regulated")
                vertical = ipnb_practices.vertical_integrate(4)
                self.assertTrue(vertical["integrated"])


if __name__ == "__main__":
    unittest.main()
