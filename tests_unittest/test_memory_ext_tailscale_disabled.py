import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.tailscale_agent import MeshNode, discover_agents


class TestMemoryExtTailscaleDisabled(unittest.TestCase):
    def test_disabled_defaults(self):
        with patch.dict(os.environ, {"OPENCLAW_TAILSCALE": "0"}, clear=False):
            self.assertEqual(discover_agents(), [])
            node = MeshNode("self")
            result = node.ping("peer")
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "tailscale_disabled")


if __name__ == "__main__":
    unittest.main()
