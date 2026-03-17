import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "scripts" / "fullscreen_idle_inhibit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fullscreen_idle_inhibit", str(MODULE_PATH))
    assert spec and spec.loader, f"Failed to load module spec for {MODULE_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFullscreenIdleInhibit(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_parse_window_ids_extracts_hex_ids(self):
        raw = "_NET_CLIENT_LIST_STACKING(WINDOW): window id # 0x2a0000a, 0x2600004, 0x1800017"
        self.assertEqual(self.mod.parse_window_ids(raw), ["0x2a0000a", "0x2600004", "0x1800017"])

    def test_is_fullscreen_state_detects_fullscreen_atom(self):
        raw = "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN, _NET_WM_STATE_FOCUSED"
        self.assertTrue(self.mod.is_fullscreen_state(raw))

    def test_detect_fullscreen_window_prefers_last_fullscreen_window(self):
        calls = []

        def fake_window_is_fullscreen(window_id):
            calls.append(window_id)
            return window_id == "0x3"

        self.mod.window_is_fullscreen = fake_window_is_fullscreen
        result = self.mod.detect_fullscreen_window(["0x1", "0x2", "0x3"])
        self.assertEqual(result, "0x3")
        self.assertEqual(calls, ["0x3"])


if __name__ == "__main__":
    unittest.main()
