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

from memory_ext.phi_tracker import log_phi, phi_score


class TestMemoryExtPhi(unittest.TestCase):
    def test_phi_score_range_stable(self):
        sections = ["alpha beta", "alpha gamma", "gamma delta"]
        first = phi_score(sections)
        second = phi_score(sections)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first["phi"], 0.0)
        self.assertLessEqual(first["phi"], 1.0)

    def test_log_respects_feature_flag(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "phi_metrics.md"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                log_phi("s1", {"phi": 0.5}, now=datetime(2026, 2, 25, tzinfo=timezone.utc))
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
