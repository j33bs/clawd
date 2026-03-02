import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.murmuration_protocol import apply_local_rule, murmurate


class TestMemoryExtMurmuration(unittest.TestCase):
    def test_fixed_state_yields_fixed_action(self):
        state = {"stress": 0.8, "energy": 0.2, "harmony": 0.1, "silence": 0.0}
        self.assertEqual(apply_local_rule(state)["action"], "moderate")
        out = murmurate(state)
        self.assertEqual(out["local_action"], "moderate")


if __name__ == "__main__":
    unittest.main()
