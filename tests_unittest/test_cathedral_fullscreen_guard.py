import types
import unittest
from unittest import mock
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime, _detect_other_fullscreen_windows


class TestCathedralFullscreenGuard(unittest.TestCase):
    def test_detect_other_fullscreen_windows_ignores_dali_window(self):
        active = types.SimpleNamespace(returncode=0, stdout="_NET_ACTIVE_WINDOW(WINDOW): window id # 0x2a00007\n", stderr="")
        details = types.SimpleNamespace(
            returncode=0,
            stdout=(
                '_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n'
                'WM_CLASS(STRING) = "DaliMirror", "DaliMirror"\n'
                '_NET_WM_NAME(UTF8_STRING) = "DALI Work Mode Consciousness Mirror"\n'
            ),
            stderr="",
        )
        with mock.patch("cathedral.runtime.subprocess.run", side_effect=[active, details]):
            windows, probe = _detect_other_fullscreen_windows()
        self.assertEqual(windows, [])
        self.assertEqual(probe, "xprop_own_window")

    def test_detect_other_fullscreen_windows_reports_foreign_window(self):
        active = types.SimpleNamespace(returncode=0, stdout="_NET_ACTIVE_WINDOW(WINDOW): window id # 0x2400012\n", stderr="")
        details = types.SimpleNamespace(
            returncode=0,
            stdout=(
                '_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n'
                'WM_CLASS(STRING) = "firefox", "Firefox"\n'
                '_NET_WM_NAME(UTF8_STRING) = "Research Dashboard"\n'
            ),
            stderr="",
        )
        with mock.patch("cathedral.runtime.subprocess.run", side_effect=[active, details]):
            windows, probe = _detect_other_fullscreen_windows()
        self.assertEqual(probe, "xprop_scan")
        self.assertEqual(windows[0]["window_id"], "0x2400012")
        self.assertEqual(windows[0]["wm_class"], 'firefox", "Firefox')

    def test_idle_update_blocks_attach_when_fullscreen_app_active(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.idle_mode_enabled = True
        runtime._manual_enter_display_mode = False
        runtime.idle_trigger_source = "gnome"
        runtime.idle_seconds = 180.0
        runtime.display_mode_active = False
        runtime.frontend = "python"
        runtime.phase1_idle_autorun_enabled = False
        runtime._phase1_idle_episode_consumed = False
        runtime.abort_if_fullscreen_active = True
        runtime.fullscreen_guard_probe = "disabled"
        runtime.fullscreen_guard_blocked = False
        runtime.fullscreen_guard_windows = []
        runtime.fullscreen_guard_reason = ""
        runtime._fullscreen_guard_log_ts = 0.0
        runtime.requested_mode = "auto"
        runtime.log = mock.Mock()
        runtime._enter_display_mode = mock.Mock()
        runtime._exit_display_mode = mock.Mock()
        runtime._probe_idle_seconds = mock.Mock(return_value=(True, 240.0))
        runtime._refresh_fullscreen_guard = mock.Mock(return_value=True)
        runtime._last_idle_wait_log_ts = 0.0

        DaliCathedralRuntime._update_idle_display_state(runtime)

        runtime._enter_display_mode.assert_not_called()
        runtime._refresh_fullscreen_guard.assert_called_once()


if __name__ == "__main__":
    unittest.main()
