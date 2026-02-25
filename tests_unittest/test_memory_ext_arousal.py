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

from memory_ext.arousal_detector import arousal_to_state, compute_arousal, get_arousal_state, modulate_response


class TestMemoryExtArousal(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(arousal_to_state(0.1), "IDLE")
        self.assertEqual(arousal_to_state(0.4), "ACTIVE")
        self.assertEqual(arousal_to_state(0.7), "ENGAGED")
        self.assertEqual(arousal_to_state(0.9), "OVERLOAD")

    def test_modulation(self):
        base = "x" * 300
        out = modulate_response(0.95, base)
        self.assertTrue(out.startswith("[CAUTION]"))
        self.assertLess(len(out), 220)

    def test_state_write_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "arousal_state.json"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                _ = get_arousal_state(10, 20, 0.1, 0.1)
                self.assertFalse(target.exists())
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                _ = get_arousal_state(10, 20, 0.1, 0.1)
                self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
