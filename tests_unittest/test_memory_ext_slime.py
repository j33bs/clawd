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

from memory_ext.slime_routing import TrailNetwork


class TestMemoryExtSlime(unittest.TestCase):
    def test_deposit_then_route(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "slime_network.json"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                net = TrailNetwork(state_path=state)
                tid = net.deposit_trail("TACTI governance routing", 1.5)
                routed = net.route_query("governance")
                self.assertIn(tid, routed)
                stats = net.get_network_state()
                self.assertEqual(stats["nodes"], 1)


if __name__ == "__main__":
    unittest.main()
