import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime, _schedule_window_allowed


class TestCathedralScheduleIdle(unittest.TestCase):
    def _make_runtime(self) -> DaliCathedralRuntime:
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.log = mock.Mock()
        runtime.schedule_enabled = True
        runtime.schedule_window_start = "17:00"
        runtime.schedule_window_end = "21:00"
        runtime.schedule_allowed = False
        runtime._last_schedule_allowed = False
        runtime.schedule_timezone = "Australia/Brisbane"
        runtime.idle_enabled = True
        runtime.idle_mode_enabled = True
        runtime.idle_seconds = 300.0
        runtime.idle_supported = True
        runtime.idle_threshold_seconds = 300.0
        runtime.idle_last_check_ok = True
        runtime.idle_last_error = ""
        runtime.active_input_suppress_seconds = 12.0
        runtime.scheduled_mouse_dismiss_guard_seconds = 6.0
        runtime.scheduled_input_stabilize_seconds = 15.0
        runtime.active_input_suppressed = False
        runtime.active_input_reason = ""
        runtime.idle_source = "session"
        runtime.session_idle_supported = True
        runtime.session_idle_seconds = 600.0
        runtime.idle_last_input_ts = "2026-03-06T00:00:00Z"
        runtime.idle_reason = "mutter"
        runtime.idle_trigger_source = "internal"
        runtime.idle_triggered = False
        runtime.idle_triggered_at = ""
        runtime.requested_mode = "auto"
        runtime.effective_mode = "auto"
        runtime.control_source = "unit_test"
        runtime.last_control_ts = "2026-03-06T00:00:00Z"
        runtime.last_control_reason = "unit_test"
        runtime.manual_override_mode = "none"
        runtime.display_mode_active = False
        runtime.display_mode_reason = "startup"
        runtime.effective_activation_source = "none"
        runtime.idle_inhibit_enabled = True
        runtime.inhibit_active = False
        runtime.inhibit_reason = ""
        runtime.display_inhibitor_active = False
        runtime.inhibitor_backend = "none"
        runtime._display_inhibitor_proc = None
        runtime._startup_force_display_mode = False
        runtime.minimum_active_seconds = 60.0
        runtime.minimum_off_seconds = 30.0
        runtime._last_display_transition_ts = 0.0
        runtime._last_idle_wait_log_ts = 0.0
        runtime._current_idle_seconds = 0.0
        runtime._load_control_state = mock.Mock()
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 600.0))
        runtime._start_display_inhibitor = mock.Mock(
            side_effect=lambda: (
                setattr(runtime, "display_inhibitor_active", True),
                setattr(runtime, "inhibit_active", True),
                setattr(runtime, "inhibit_reason", "Dali Cathedral display mode"),
            )
        )
        runtime._stop_display_inhibitor = mock.Mock(
            side_effect=lambda: (
                setattr(runtime, "display_inhibitor_active", False),
                setattr(runtime, "inhibit_active", False),
                setattr(runtime, "inhibit_reason", ""),
            )
        )
        return runtime

    def test_schedule_window_logic(self):
        inside = datetime(2026, 3, 6, 17, 30, tzinfo=timezone.utc)
        outside = datetime(2026, 3, 6, 21, 0, tzinfo=timezone.utc)
        self.assertTrue(_schedule_window_allowed(inside, start="17:00", end="21:00"))
        self.assertFalse(_schedule_window_allowed(outside, start="17:00", end="21:00"))

    def test_manual_override_on_off_auto(self):
        runtime = self._make_runtime()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))

        runtime.manual_override_mode = "on"
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertTrue(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "manual_on")

        runtime.manual_override_mode = "off"
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertFalse(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "manual_off")

        runtime.manual_override_mode = "none"
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertTrue(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "schedule_idle")

    def test_display_mode_reason_transitions(self):
        runtime = self._make_runtime()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 22, 0, tzinfo=timezone.utc))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertFalse(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "outside_window")

        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertTrue(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "schedule_idle")

    def test_recent_input_suppresses_schedule_window_activation(self):
        runtime = self._make_runtime()
        runtime.schedule_latch_display = True
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 2.0))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertFalse(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "active_input")
        self.assertTrue(runtime.active_input_suppressed)
        self.assertEqual(runtime.effective_activation_source, "none")

    def test_active_input_bypasses_minimum_active_hysteresis(self):
        runtime = self._make_runtime()
        runtime.schedule_latch_display = True
        runtime.display_mode_active = True
        runtime._last_display_transition_ts = __import__("time").monotonic()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 1.0))
        runtime._evaluate_display_mode_state(force=False, allow_hysteresis=True)
        self.assertFalse(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "active_input")

    def test_schedule_latch_reentry_bypasses_minimum_off_hysteresis(self):
        runtime = self._make_runtime()
        runtime.schedule_latch_display = True
        runtime.display_mode_active = False
        runtime._last_display_transition_ts = __import__("time").monotonic()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 20.0))
        runtime._evaluate_display_mode_state(force=False, allow_hysteresis=True)
        self.assertTrue(runtime.display_mode_active)
        self.assertEqual(runtime.display_mode_reason, "schedule_window")

    def test_scheduled_activation_ignores_programmatic_idle_reset_briefly(self):
        runtime = self._make_runtime()
        runtime.schedule_latch_display = True
        runtime.display_mode_active = True
        runtime.effective_activation_source = "scheduled_window"
        runtime._display_enter_monotonic = __import__("time").monotonic()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 2.0))
        runtime._evaluate_display_mode_state(force=False, allow_hysteresis=True)
        self.assertTrue(runtime.display_mode_active)
        self.assertFalse(runtime.active_input_suppressed)

    def test_schedule_idle_reason_grants_programmatic_idle_reset_grace(self):
        runtime = self._make_runtime()
        runtime.schedule_latch_display = False
        runtime.display_mode_active = True
        runtime.display_mode_reason = "schedule_idle"
        runtime.effective_activation_source = "none"
        runtime._display_enter_monotonic = __import__("time").monotonic()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 1.0))
        runtime._evaluate_display_mode_state(force=False, allow_hysteresis=True)
        self.assertTrue(runtime.display_mode_active)
        self.assertFalse(runtime.active_input_suppressed)

    def test_scheduled_mouse_dismiss_guard_ignores_early_mouse_move(self):
        runtime = self._make_runtime()
        runtime.effective_activation_source = "scheduled_window"
        runtime._display_enter_monotonic = __import__("time").monotonic()
        self.assertTrue(runtime._should_ignore_display_dismiss("mouse_move"))
        self.assertFalse(runtime._should_ignore_display_dismiss("key_press"))

    def test_scheduled_mouse_dismiss_guard_expires(self):
        runtime = self._make_runtime()
        runtime.effective_activation_source = "scheduled_idle"
        runtime._display_enter_monotonic = __import__("time").monotonic() - 10.0
        self.assertFalse(runtime._should_ignore_display_dismiss("mouse_move"))

    def test_inhibit_flag_transitions(self):
        runtime = self._make_runtime()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertTrue(runtime.display_mode_active)
        self.assertTrue(runtime.inhibit_active)
        self.assertEqual(runtime.inhibit_reason, "Dali Cathedral display mode")
        runtime.manual_override_mode = "off"
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertFalse(runtime.display_mode_active)
        self.assertFalse(runtime.inhibit_active)
        self.assertEqual(runtime.inhibit_reason, "")

    def test_session_idle_state_fields_present(self):
        runtime = self._make_runtime()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertEqual(runtime.idle_source, "session")
        self.assertTrue(runtime.session_idle_supported)
        self.assertGreaterEqual(runtime.session_idle_seconds, 0.0)
        self.assertEqual(runtime.idle_reason, "mutter")

    def test_manual_override_precedence_over_schedule_idle(self):
        runtime = self._make_runtime()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 18, 0, tzinfo=timezone.utc))
        runtime.manual_override_mode = "off"
        runtime.requested_mode = "off"
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertFalse(runtime.display_mode_active)
        self.assertEqual(runtime.effective_activation_source, "manual_off")

    def test_effective_activation_source_contract(self):
        runtime = self._make_runtime()
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 22, 0, tzinfo=timezone.utc))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertEqual(runtime.effective_activation_source, "none")
        runtime.manual_override_mode = "on"
        runtime.requested_mode = "on"
        runtime._schedule_now = mock.Mock(return_value=datetime(2026, 3, 6, 22, 1, tzinfo=timezone.utc))
        runtime._evaluate_display_mode_state(force=True, allow_hysteresis=False)
        self.assertEqual(runtime.effective_activation_source, "manual_on")

    def test_control_state_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_path = Path(tmpdir) / "fishtank_control_state.json"
            runtime = self._make_runtime()
            runtime._control_state_path = control_path
            runtime._control_state_lock = threading.Lock()
            runtime._capture_control_state = DaliCathedralRuntime._capture_control_state.__get__(runtime, DaliCathedralRuntime)
            runtime._persist_control_state = DaliCathedralRuntime._persist_control_state.__get__(runtime, DaliCathedralRuntime)
            runtime._load_control_state = DaliCathedralRuntime._load_control_state.__get__(runtime, DaliCathedralRuntime)

            runtime.manual_override_mode = "on"
            runtime.requested_mode = "on"
            runtime._persist_control_state(source="unit_test", reason="persist_on")

            reloaded = self._make_runtime()
            reloaded._control_state_path = control_path
            reloaded._control_state_lock = threading.Lock()
            reloaded._capture_control_state = DaliCathedralRuntime._capture_control_state.__get__(reloaded, DaliCathedralRuntime)
            reloaded._load_control_state = DaliCathedralRuntime._load_control_state.__get__(reloaded, DaliCathedralRuntime)
            reloaded.manual_override_mode = "none"
            reloaded.requested_mode = "auto"
            reloaded._control_state_mtime_ns = 0
            reloaded._load_control_state(force=True)

            self.assertEqual(reloaded.manual_override_mode, "on")


if __name__ == "__main__":
    unittest.main()
