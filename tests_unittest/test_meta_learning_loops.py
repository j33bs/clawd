import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.meta_learning_loops import MetaLoop


class TestMetaLearningLoops(unittest.TestCase):
    def test_process_interaction_deterministic(self):
        loop = MetaLoop()
        out = loop.process_interaction(
            {
                "failed": True,
                "failure_event": "timeout",
                "lesson": "increase backoff",
                "prediction": 0.2,
                "observed": 0.6,
                "friction_type": "latency",
                "context": "router",
                "response": "retry",
            }
        )
        self.assertIn("updated", out)
        self.assertIn("signals", out)
        self.assertGreaterEqual(out["calibration_score"], 0.0)

    def test_off_by_default_no_log_write(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "meta_learning_loops.jsonl"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                loop = MetaLoop()
                loop.process_interaction({"prediction": 0.1, "observed": 0.1})
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
