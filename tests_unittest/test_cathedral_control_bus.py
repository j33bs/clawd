import tempfile
import time
import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.control_bus import ControlBus


class TestControlBus(unittest.TestCase):
    def test_control_bus_ttl_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "control_bus_state.json"
            bus = ControlBus(state_path=state_path)
            bus.set_transient(name="exposure_boost", value=2.0, ttl_seconds=0.05)
            self.assertGreater(bus.get_value("exposure_boost", 0.0), 1.9)
            time.sleep(0.08)
            self.assertEqual(bus.get_value("exposure_boost", 0.0), 0.0)
            self.assertEqual(bus.active_transient(), {})


if __name__ == "__main__":
    unittest.main()
