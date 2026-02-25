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

from memory_ext.reservoir import EchoState


class TestMemoryExtReservoir(unittest.TestCase):
    def test_deterministic_with_seed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "reservoir_state.json"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                a = EchoState(seed=7, dim=8, state_path=path)
                b = EchoState(seed=7, dim=8, state_path=path)
                self.assertEqual(len(a.state), 8)
                one = a.predict_next_state("hello world")
                b.state = [0.0] * 8
                b.inputs = []
                b.step = 0
                two = b.predict_next_state("hello world")
                self.assertAlmostEqual(one, two, places=8)

    def test_off_by_default_no_state_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "reservoir_state.json"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                e = EchoState(seed=1, state_path=path)
                e.predict_next_state("x")
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
