import subprocess
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime


class TestCathedralInhibitorStack(unittest.TestCase):
    def _runtime_stub(self) -> DaliCathedralRuntime:
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.log = mock.Mock()
        runtime.idle_inhibit_enabled = True
        runtime.inhibit_reason = ""
        runtime.inhibit_active = False
        runtime.display_inhibitor_active = False
        runtime.inhibitor_backend = "none"
        runtime.inhibitor_backends = []
        runtime.display_blank_inhibit_active = False
        runtime.screensaver_inhibit_active = False
        runtime.session_inhibit_active = False
        runtime.dpms_override_active = False
        runtime._display_inhibitor_proc = None
        runtime._screensaver_inhibit_cookie = None
        runtime._session_inhibit_cookie = None
        runtime._x11_dpms_override_applied = False
        runtime._x11_restore_commands = []
        runtime._read_json = mock.Mock(return_value={})
        runtime._schedule_now = mock.Mock()
        runtime.schedule_slots = []
        runtime.lease_owner = "unit-test-owner"
        runtime.requested_mode = "auto"
        runtime.effective_mode = "auto"
        runtime.control_source = "unit_test"
        runtime.last_control_ts = ""
        runtime.last_control_reason = ""
        runtime.last_control_apply_ts = ""
        runtime.last_idle_activation_ts = ""
        runtime.schedule_enabled = True
        runtime.schedule_allowed = True
        runtime.schedule_window_start = "17:00"
        runtime.schedule_window_end = "21:00"
        runtime.schedule_timezone = "Australia/Brisbane"
        runtime.idle_enabled = True
        runtime.idle_mode_enabled = True
        runtime.idle_seconds = 300.0
        runtime.idle_supported = True
        runtime.idle_threshold_seconds = 300.0
        runtime.idle_last_check_ok = True
        runtime.idle_last_error = ""
        runtime.idle_source = "session"
        runtime.session_idle_supported = True
        runtime.session_idle_seconds = 0.0
        runtime.idle_last_input_ts = ""
        runtime.idle_reason = "mutter"
        runtime.idle_triggered = False
        runtime.idle_trigger_source = "session"
        runtime.idle_triggered_at = ""
        runtime.manual_override_mode = "none"
        runtime.display_mode_active = False
        runtime.display_mode_reason = "startup"
        runtime.effective_activation_source = "none"
        runtime.runtime_instance_id = "cathedral-test"
        runtime.pid = 1234
        runtime.runtime_start_ts = "2026-03-06T00:00:00Z"
        return runtime

    def test_start_display_inhibitor_stacks_available_backends(self):
        runtime = self._runtime_stub()
        proc = mock.Mock()
        proc.poll.return_value = None
        with mock.patch("cathedral.runtime.subprocess.Popen", return_value=proc):
            runtime._acquire_screensaver_inhibit = mock.Mock(
                side_effect=lambda: (
                    setattr(runtime, "_screensaver_inhibit_cookie", 101),
                    True,
                )[1]
            )
            runtime._acquire_session_inhibit = mock.Mock(
                side_effect=lambda: (
                    setattr(runtime, "_session_inhibit_cookie", 202),
                    True,
                )[1]
            )
            runtime._acquire_x11_dpms_override = mock.Mock(
                side_effect=lambda: (
                    setattr(runtime, "_x11_dpms_override_applied", True),
                    True,
                )[1]
            )
            runtime._start_display_inhibitor()
        self.assertTrue(runtime.inhibit_active)
        self.assertTrue(runtime.display_inhibitor_active)
        self.assertIn("systemd-inhibit-child", runtime.inhibitor_backends)
        self.assertIn("dbus-screensaver", runtime.inhibitor_backends)
        self.assertIn("dbus-gnome-session", runtime.inhibitor_backends)
        self.assertIn("x11-dpms", runtime.inhibitor_backends)
        self.assertTrue(runtime.display_blank_inhibit_active)
        self.assertTrue(runtime.screensaver_inhibit_active)
        self.assertTrue(runtime.session_inhibit_active)
        self.assertTrue(runtime.dpms_override_active)

    def test_start_display_inhibitor_falls_back_when_systemd_unavailable(self):
        runtime = self._runtime_stub()
        with mock.patch("cathedral.runtime.subprocess.Popen", side_effect=OSError("missing-systemd-inhibit")):
            runtime._acquire_screensaver_inhibit = mock.Mock(return_value=False)
            runtime._acquire_session_inhibit = mock.Mock(return_value=False)
            runtime._acquire_x11_dpms_override = mock.Mock(
                side_effect=lambda: (
                    setattr(runtime, "_x11_dpms_override_applied", True),
                    True,
                )[1]
            )
            runtime._start_display_inhibitor()
        self.assertTrue(runtime.inhibit_active)
        self.assertEqual(runtime.inhibitor_backend, "x11-dpms")
        self.assertEqual(runtime.inhibitor_backends, ["x11-dpms"])
        self.assertTrue(runtime.display_blank_inhibit_active)
        self.assertTrue(runtime.dpms_override_active)

    def test_stop_display_inhibitor_releases_all_backends(self):
        runtime = self._runtime_stub()
        proc = mock.Mock()
        proc.poll.return_value = None
        runtime._display_inhibitor_proc = proc
        runtime._screensaver_inhibit_cookie = 77
        runtime._session_inhibit_cookie = 88
        runtime._x11_dpms_override_applied = True
        runtime._x11_restore_commands = [["xset", "+dpms"], ["xset", "s", "on"]]
        runtime.inhibit_reason = "Dali Cathedral display mode"
        runtime._sync_inhibitor_state()
        runtime._run_inhibitor_cmd = mock.Mock(return_value=subprocess.CompletedProcess(args=["ok"], returncode=0, stdout="", stderr=""))
        runtime._stop_display_inhibitor()
        self.assertFalse(runtime.inhibit_active)
        self.assertFalse(runtime.display_inhibitor_active)
        self.assertEqual(runtime.inhibitor_backend, "none")
        self.assertEqual(runtime.inhibitor_backends, [])
        self.assertFalse(runtime.display_blank_inhibit_active)
        self.assertFalse(runtime.screensaver_inhibit_active)
        self.assertFalse(runtime.session_inhibit_active)
        self.assertFalse(runtime.dpms_override_active)
        self.assertIsNone(runtime._screensaver_inhibit_cookie)
        self.assertIsNone(runtime._session_inhibit_cookie)
        self.assertFalse(runtime._x11_dpms_override_applied)

    def test_runtime_state_exports_inhibitor_stack_fields(self):
        runtime = self._runtime_stub()
        runtime._display_inhibitor_proc = mock.Mock()
        runtime._display_inhibitor_proc.poll.return_value = None
        runtime._screensaver_inhibit_cookie = 5
        runtime._session_inhibit_cookie = 6
        runtime._x11_dpms_override_applied = True
        state = DaliCathedralRuntime._runtime_state_fields(runtime)
        for key in (
            "inhibitor_backends",
            "display_blank_inhibit_active",
            "screensaver_inhibit_active",
            "session_inhibit_active",
            "dpms_override_active",
        ):
            self.assertIn(key, state)
        self.assertTrue(state["inhibit_active"])
        self.assertGreaterEqual(len(state["inhibitor_backends"]), 3)


if __name__ == "__main__":
    unittest.main()
