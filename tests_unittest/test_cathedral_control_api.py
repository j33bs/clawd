import json
import types
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral import control_api
from cathedral.runtime import DaliCathedralRuntime


class TestCathedralControlApi(unittest.TestCase):
    def test_control_api_on_off_auto_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_path = Path(tmpdir) / "fishtank_control_state.json"
            state_path = Path(tmpdir) / "fishtank_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "requested_mode": "auto",
                        "effective_mode": "auto",
                        "display_mode_active": False,
                        "last_control_ts": "",
                    }
                ),
                encoding="utf-8",
            )

            off_result = control_api.set_mode("off", source="unit_test", wait=False, control_path=control_path, state_path=state_path)
            self.assertTrue(off_result["ok"])
            self.assertEqual(control_api.load_control_state(control_path)["requested_mode"], "off")

            on_result = control_api.set_mode("on", source="unit_test", wait=False, control_path=control_path, state_path=state_path)
            self.assertTrue(on_result["ok"])
            self.assertEqual(control_api.load_control_state(control_path)["requested_mode"], "on")

            auto_result = control_api.set_mode("auto", source="unit_test", wait=False, control_path=control_path, state_path=state_path)
            self.assertTrue(auto_result["ok"])
            self.assertEqual(control_api.load_control_state(control_path)["requested_mode"], "auto")

    def test_runtime_consumes_control_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_path = Path(tmpdir) / "fishtank_control_state.json"
            control_api.write_control_state("off", source="unit_test", reason="runtime_consume", path=control_path)
            runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
            runtime.log = mock.Mock()
            runtime._control_state_path = control_path
            runtime._control_state_mtime_ns = 0
            runtime.requested_mode = "auto"
            runtime.effective_mode = "auto"
            runtime.control_source = ""
            runtime.last_control_ts = ""
            runtime.last_control_reason = ""
            runtime.manual_override_mode = "none"
            runtime._capture_control_state = DaliCathedralRuntime._capture_control_state.__get__(runtime, DaliCathedralRuntime)
            runtime._load_control_state = DaliCathedralRuntime._load_control_state.__get__(runtime, DaliCathedralRuntime)
            runtime._load_control_state(force=True)
            self.assertEqual(runtime.requested_mode, "off")
            self.assertEqual(runtime.effective_mode, "off")
            self.assertEqual(runtime.manual_override_mode, "off")
            self.assertEqual(runtime.control_source, "unit_test")
            self.assertEqual(runtime.last_control_reason, "runtime_consume")

    def test_fishtank_state_reports_requested_and_effective_mode(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime._read_json = mock.Mock(return_value={})
        runtime._schedule_now = mock.Mock()
        runtime.lease_owner = "test-owner"
        runtime.runtime_instance_id = "cathedral-test-instance"
        runtime.pid = 12345
        runtime.runtime_start_ts = "2026-03-06T00:00:00Z"
        runtime.requested_mode = "auto"
        runtime.effective_mode = "auto"
        runtime.control_source = "unit_test"
        runtime.last_control_ts = "2026-03-06T00:00:00Z"
        runtime.last_control_reason = "status"
        runtime.last_control_apply_ts = "2026-03-06T00:00:01Z"
        runtime.last_idle_activation_ts = ""
        runtime.schedule_enabled = True
        runtime.schedule_allowed = False
        runtime.schedule_latch_display = True
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
        runtime.session_idle_seconds = 42.0
        runtime.idle_last_input_ts = "2026-03-06T00:00:00Z"
        runtime.idle_reason = "mutter"
        runtime.idle_triggered = False
        runtime.idle_trigger_source = "session"
        runtime.idle_triggered_at = ""
        runtime.manual_override_mode = "none"
        runtime.display_mode_active = False
        runtime.display_mode_reason = "schedule_idle"
        runtime.effective_activation_source = "none"
        runtime.inhibit_active = False
        runtime.inhibit_reason = ""
        runtime.idle_inhibit_enabled = True
        runtime.display_inhibitor_active = False
        runtime.inhibitor_backend = "none"
        state = DaliCathedralRuntime._runtime_state_fields(runtime)
        self.assertEqual(state["requested_mode"], "auto")
        self.assertEqual(state["effective_mode"], "auto")
        self.assertEqual(state["control_source"], "unit_test")
        self.assertEqual(state["runtime_instance_id"], "cathedral-test-instance")
        self.assertEqual(state["pid"], 12345)
        self.assertIn("idle_supported", state)
        self.assertIn("idle_last_check_ok", state)
        self.assertIn("schedule_latch_display", state)

    def test_runtime_state_includes_runtime_instance_id(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime._read_json = mock.Mock(return_value={})
        runtime._schedule_now = mock.Mock()
        runtime.lease_owner = "test-owner"
        runtime.runtime_instance_id = "cathedral-test-instance"
        runtime.pid = 2468
        runtime.runtime_start_ts = "2026-03-06T12:00:00Z"
        runtime.requested_mode = "auto"
        runtime.effective_mode = "auto"
        runtime.control_source = "unit_test"
        runtime.last_control_ts = ""
        runtime.last_control_reason = ""
        runtime.last_control_apply_ts = ""
        runtime.last_idle_activation_ts = ""
        runtime.schedule_enabled = True
        runtime.schedule_allowed = False
        runtime.schedule_latch_display = True
        runtime.schedule_window_start = "17:00"
        runtime.schedule_window_end = "21:00"
        runtime.schedule_timezone = "Australia/Brisbane"
        runtime.idle_enabled = True
        runtime.idle_mode_enabled = True
        runtime.idle_seconds = 300.0
        runtime.idle_supported = False
        runtime.idle_threshold_seconds = 300.0
        runtime.idle_last_check_ok = True
        runtime.idle_last_error = ""
        runtime.idle_source = "session"
        runtime.session_idle_supported = False
        runtime.session_idle_seconds = 0.0
        runtime.idle_last_input_ts = ""
        runtime.idle_reason = "startup"
        runtime.idle_triggered = False
        runtime.idle_trigger_source = "session"
        runtime.idle_triggered_at = ""
        runtime.manual_override_mode = "none"
        runtime.display_mode_active = False
        runtime.display_mode_reason = "startup"
        runtime.effective_activation_source = "none"
        runtime.inhibit_active = False
        runtime.inhibit_reason = ""
        runtime.idle_inhibit_enabled = True
        runtime.display_inhibitor_active = False
        runtime.inhibitor_backend = "none"
        state = DaliCathedralRuntime._runtime_state_fields(runtime)
        self.assertEqual(state["runtime_instance_id"], "cathedral-test-instance")
        self.assertEqual(state["pid"], 2468)
        self.assertEqual(state["start_ts"], "2026-03-06T12:00:00Z")

    def test_runtime_prefers_monitor_refresh_for_display_loop_rate(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.rate_hz = 30.0
        runtime.display_rate_hz = 120.0
        runtime.display_rate_mode = "monitor"
        runtime.renderer = types.SimpleNamespace(selected_refresh_hz=120.0, monitor_refresh_hz=60.0)
        rate_hz, source = DaliCathedralRuntime._resolve_loop_rate_hz(runtime, display_active=True)
        self.assertEqual(rate_hz, 120.0)
        self.assertEqual(source, "monitor_refresh")

    def test_schedule_window_latch_keeps_display_active_in_auto(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.log = mock.Mock()
        runtime._runtime_instance_id = mock.Mock(return_value="cathedral-test-instance")
        runtime._runtime_pid = mock.Mock(return_value=1234)
        runtime._load_control_state = mock.Mock()
        runtime._schedule_now = mock.Mock(return_value=__import__("datetime").datetime(2026, 3, 7, 18, 0))
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 12.0))
        runtime.schedule_enabled = True
        runtime.schedule_window_start = "17:00"
        runtime.schedule_window_end = "21:00"
        runtime.schedule_slots = []
        runtime.schedule_timezone = "Australia/Brisbane"
        runtime._startup_force_display_mode = False
        runtime.manual_override_mode = "none"
        runtime.schedule_allowed = True
        runtime.schedule_latch_display = True
        runtime.idle_enabled = True
        runtime.idle_triggered = False
        runtime.idle_trigger_source = "session"
        runtime.requested_mode = "auto"
        runtime.display_mode_active = False
        runtime.display_mode_reason = "startup"
        runtime.effective_activation_source = "none"
        runtime.effective_mode = "auto"
        runtime._last_display_transition_ts = 0.0
        runtime._last_schedule_allowed = True
        runtime._last_idle_wait_log_ts = time.monotonic()
        runtime.minimum_off_seconds = 0.0
        runtime.minimum_active_seconds = 0.0
        runtime._current_idle_seconds = 12.0
        runtime.idle_seconds = 60.0
        runtime._enter_display_mode = mock.Mock(side_effect=lambda reason: setattr(runtime, 'display_mode_active', True))
        runtime._exit_display_mode = mock.Mock()

        DaliCathedralRuntime._evaluate_display_mode_state(runtime, force=False, allow_hysteresis=False)

        runtime._enter_display_mode.assert_called_once_with(reason="schedule_window")
        self.assertEqual(runtime.effective_activation_source, "scheduled_window")

    def test_runtime_state_exports_loop_rate_fields(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime._read_json = mock.Mock(return_value={})
        runtime._schedule_now = mock.Mock()
        runtime.lease_owner = "test-owner"
        runtime.runtime_instance_id = "cathedral-test-instance"
        runtime.pid = 2468
        runtime.runtime_start_ts = "2026-03-06T12:00:00Z"
        runtime.requested_mode = "on"
        runtime.effective_mode = "on"
        runtime.control_source = "unit_test"
        runtime.last_control_ts = ""
        runtime.last_control_reason = ""
        runtime.last_control_apply_ts = ""
        runtime.last_idle_activation_ts = ""
        runtime.schedule_enabled = True
        runtime.schedule_allowed = True
        runtime.schedule_latch_display = True
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
        runtime.session_idle_seconds = 42.0
        runtime.idle_last_input_ts = ""
        runtime.idle_reason = "mutter"
        runtime.idle_triggered = True
        runtime.idle_trigger_source = "session"
        runtime.idle_triggered_at = ""
        runtime.manual_override_mode = "on"
        runtime.display_mode_active = True
        runtime.display_mode_reason = "manual_on"
        runtime.effective_activation_source = "manual_on"
        runtime.inhibit_active = True
        runtime.inhibit_reason = "Dali Cathedral display mode"
        runtime.idle_inhibit_enabled = True
        runtime.display_inhibitor_active = True
        runtime.inhibitor_backend = "systemd-inhibit-child"
        runtime.rate_hz = 30.0
        runtime.display_rate_hz = 120.0
        runtime.display_rate_mode = "monitor"
        runtime.loop_rate_target_hz = 120.0
        runtime.loop_rate_source = "monitor_refresh"
        runtime.loop_sleep_ms = 2.5
        runtime.rate_limited = True
        state = DaliCathedralRuntime._runtime_state_fields(runtime)
        self.assertEqual(state["base_rate_hz"], 30.0)
        self.assertEqual(state["display_rate_cap_hz"], 120.0)
        self.assertEqual(state["display_rate_mode"], "monitor")
        self.assertEqual(state["loop_rate_target_hz"], 120.0)
        self.assertEqual(state["loop_rate_source"], "monitor_refresh")
        self.assertEqual(state["loop_sleep_ms"], 2.5)
        self.assertTrue(state["rate_limited"])

    def test_control_api_returns_instance_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_path = Path(tmpdir) / "fishtank_control_state.json"
            state_path = Path(tmpdir) / "fishtank_state.json"
            control_api.write_control_state("on", source="unit_test", reason="instance_id", path=control_path)
            state_path.write_text(
                json.dumps(
                    {
                        "requested_mode": "on",
                        "effective_mode": "on",
                        "display_mode_active": True,
                        "display_attached": True,
                        "window_visible": True,
                        "fullscreen_requested": True,
                        "fullscreen_attached": True,
                        "monitor_bound": True,
                        "runtime_instance_id": "cathedral-test-instance",
                        "pid": 12345,
                        "start_ts": "2026-03-06T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            status = control_api.get_status(control_path=control_path, state_path=state_path)
            self.assertEqual(status["runtime_instance_id"], "cathedral-test-instance")
            self.assertEqual(status["pid"], 12345)
            self.assertTrue(status["visible_display_ok"])

    def test_agent_path_uses_canonical_control_entrypoint(self):
        wrapper = (REPO_ROOT / "tools" / "cathedralctl").read_text(encoding="utf-8")
        self.assertIn("python3 -m cathedral.control_api", wrapper)
        self.assertIn("--source agent", wrapper)
        self.assertIn("--wait-visible", wrapper)
        self.assertIn("--wait-hidden", wrapper)
        self.assertIn("DALI_FISHTANK_QUIESCE_UNITS", wrapper)
        self.assertIn("openclaw-vllm.service", wrapper)

    def test_agent_wait_visible_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_path = Path(tmpdir) / "fishtank_control_state.json"
            state_path = Path(tmpdir) / "fishtank_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "requested_mode": "on",
                        "effective_mode": "on",
                        "display_mode_active": True,
                        "display_attached": False,
                        "window_visible": False,
                        "fullscreen_requested": True,
                        "fullscreen_attached": False,
                        "monitor_bound": False,
                        "last_control_ts": "",
                    }
                ),
                encoding="utf-8",
            )
            result = control_api.set_mode(
                "on",
                source="unit_test",
                wait=True,
                wait_for="visible",
                wait_timeout_s=0.3,
                control_path=control_path,
                state_path=state_path,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "runtime_not_applied_within_timeout")

    def test_idle_activation_requires_display_attach(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            control_path = Path(tmpdir) / "fishtank_control_state.json"
            state_path = Path(tmpdir) / "fishtank_state.json"
            control_api.write_control_state("auto", source="unit_test", reason="idle_attach_contract", path=control_path)
            state_path.write_text(
                json.dumps(
                    {
                        "requested_mode": "auto",
                        "effective_mode": "auto",
                        "effective_activation_source": "scheduled_idle",
                        "idle_triggered": True,
                        "display_mode_active": True,
                        "display_attached": False,
                        "window_visible": False,
                        "fullscreen_requested": True,
                        "fullscreen_attached": False,
                        "monitor_bound": False,
                    }
                ),
                encoding="utf-8",
            )
            status = control_api.get_status(control_path=control_path, state_path=state_path)
            self.assertFalse(status["visible_display_ok"])

    def test_idle_state_fields_present(self):
        status = control_api.get_status(
            control_path=Path(tempfile.gettempdir()) / "cathedral_control_api_status_control.json",
            state_path=Path(tempfile.gettempdir()) / "cathedral_control_api_status_state.json",
        )
        self.assertIn("requested_mode", status)
        self.assertIn("effective_mode", status)
        self.assertIn("display_mode_active", status)

    def test_phase1_frontend_completion_exits_auto_mode(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.frontend = "phase1"
        runtime.display_mode_active = True
        runtime.frontend_process_running = False
        runtime.frontend_activation_pending = False
        runtime.frontend_last_exit_code = 0
        runtime.frontend_last_status = "succeeded"
        runtime.requested_mode = "auto"
        runtime.last_control_ts_runtime = "2026-03-09T00:00:00Z"
        runtime._phase1_requested_mode_on_consumed_ts = ""
        runtime._sync_frontend_status_from_file = mock.Mock()
        runtime._exit_display_mode = mock.Mock()

        DaliCathedralRuntime._handle_phase1_frontend_completion(runtime)

        runtime._exit_display_mode.assert_called_once_with(reason="phase1_complete")

    def test_phase1_manual_on_latch_blocks_rerun_for_same_control_timestamp(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.frontend = "phase1"
        runtime.display_mode_active = False
        runtime.runtime_start_ts = "2026-03-09T00:00:00Z"
        runtime._phase1_requested_mode_on_consumed_ts = "2026-03-09T00:00:00Z"
        runtime._enter_display_mode = mock.Mock()

        with mock.patch(
            "cathedral.runtime.load_fishtank_control_state",
            return_value={
                "requested_mode": "on",
                "control_source": "unit_test",
                "last_control_ts": "2026-03-09T00:00:00Z",
                "last_control_reason": "manual_phase1",
            },
        ):
            applied = DaliCathedralRuntime._apply_requested_mode_override(runtime)

        self.assertTrue(applied)
        runtime._enter_display_mode.assert_not_called()

    def test_verifier_requires_visible_attach_proof(self):
        script = (REPO_ROOT / "tools" / "verify_dali_fishtank_live.sh").read_text(encoding="utf-8")
        self.assertIn("visible_display_status", script)
        self.assertIn("FAIL_NOT_VISIBLE", script)


if __name__ == "__main__":
    unittest.main()
