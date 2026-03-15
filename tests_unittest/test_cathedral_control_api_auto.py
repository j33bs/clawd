import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.control_api import load_control_state, set_mode


class TestCathedralControlApiAuto(unittest.TestCase):
    def test_auto_wait_accepts_active_effective_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            control_path = root / "control.json"
            state_path = root / "state.json"
            with mock.patch("cathedral.control_api.load_live_state") as load_live_state_mock:
                def _live_state(_path=None):
                    control_state = load_control_state(control_path)
                    return {
                        "requested_mode": "auto",
                        "effective_mode": "on",
                        "display_mode_active": True,
                        "last_control_ts": control_state["last_control_ts"],
                    }

                load_live_state_mock.side_effect = _live_state
                result = set_mode(
                    "auto",
                    source="unit_test",
                    reason="set_mode:auto",
                    wait=True,
                    wait_timeout_s=0.5,
                    control_path=control_path,
                    state_path=state_path,
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_mode"], "auto")
        self.assertEqual(result["effective_mode"], "on")


if __name__ == "__main__":
    unittest.main()
