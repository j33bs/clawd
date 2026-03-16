import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import GPUUnavailableError
from cathedral.runtime import DaliCathedralRuntime, _resolve_telegram_config


class TestCathedralRuntimeGPURequired(unittest.TestCase):
    def test_missing_moderngl_fails_closed_when_gpu_required(self):
        with mock.patch("cathedral.fishtank_renderer.moderngl", None), mock.patch(
            "cathedral.runtime.GPULease.acquire", return_value=True
        ), mock.patch("cathedral.runtime.GPULease.release", return_value=True):
            with self.assertRaises(GPUUnavailableError):
                DaliCathedralRuntime(
                    headless=True,
                    require_gpu=True,
                    telegram_enabled=False,
                )

    def test_resolve_telegram_config_logs_missing_env_when_enabled(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DALI_FISHTANK_TELEGRAM_ENABLED": "",
                "DALI_FISHTANK_TELEGRAM_TOKEN": "",
                "DALI_FISHTANK_TELEGRAM_ALLOWLIST": "",
                "DALI_FISHTANK_TELEGRAM_AUTOCLEAR_WEBHOOK": "0",
                "DALI_FISHTANK_TELEGRAM_DEBUG_DRAIN": "0",
            },
            clear=False,
        ):
            with mock.patch("cathedral.runtime.JsonlLogger.log") as log_mock:
                cfg = _resolve_telegram_config()
        self.assertTrue(cfg["enabled_requested"])
        self.assertFalse(cfg["enabled_effective"])
        self.assertEqual(cfg["token"], "")
        self.assertEqual(cfg["allowlist"], [])
        self.assertFalse(cfg["autoclear_webhook"])
        self.assertFalse(cfg["debug_drain"])
        log_mock.assert_any_call(
            "telegram_disabled_missing_env",
            token_present=False,
            chat_id_present=False,
            enabled_flag=True,
            missing_keys=["DALI_FISHTANK_TELEGRAM_TOKEN", "DALI_FISHTANK_TELEGRAM_ALLOWLIST"],
            env_file=mock.ANY,
        )

    def test_runtime_startup_blocks_when_other_fullscreen_window_active(self):
        with mock.patch.dict(
            "os.environ",
            {"DALI_FISHTANK_ABORT_IF_FULLSCREEN_ACTIVE": "1"},
            clear=False,
        ), mock.patch(
            "cathedral.runtime._detect_other_fullscreen_windows",
            return_value=([{"window_id": "0x2400012", "title": "\"Firefox\"", "wm_class": "\"firefox\", \"Firefox\""}], "xprop_scan"),
        ):
            with self.assertRaisesRegex(RuntimeError, "fullscreen application active"):
                DaliCathedralRuntime(
                    headless=False,
                    require_gpu=False,
                    telegram_enabled=False,
                )

    def test_runtime_headless_bypasses_fullscreen_guard(self):
        fake_renderer = mock.Mock()
        fake_renderer.set_runtime_context = mock.Mock()
        fake_renderer.headless = True
        fake_renderer.active_renderer_id = "test"
        with mock.patch.dict(
            "os.environ",
            {"DALI_FISHTANK_ABORT_IF_FULLSCREEN_ACTIVE": "1"},
            clear=False,
        ), mock.patch(
            "cathedral.runtime._detect_other_fullscreen_windows",
            return_value=([{"window_id": "0x2400012", "title": "\"Firefox\"", "wm_class": "\"firefox\", \"Firefox\""}], "xprop_scan"),
        ), mock.patch(
            "cathedral.runtime.GPULease.acquire", return_value=True
        ), mock.patch(
            "cathedral.runtime.GPULease.release", return_value=True
        ), mock.patch(
            "cathedral.runtime.FishTankRenderer", return_value=fake_renderer
        ):
            runtime = DaliCathedralRuntime(
                headless=True,
                require_gpu=False,
                telegram_enabled=False,
            )
        self.assertEqual(runtime.fullscreen_guard_probe, "headless_bypass")

    def test_runtime_ignores_own_ue_frontend_window_in_fullscreen_guard(self):
        fake_renderer = mock.Mock()
        fake_renderer.set_runtime_context = mock.Mock()
        fake_renderer.headless = True
        fake_renderer.active_renderer_id = "test"
        with mock.patch.dict(
            "os.environ",
            {"DALI_FISHTANK_ABORT_IF_FULLSCREEN_ACTIVE": "1"},
            clear=False,
        ), mock.patch(
            "cathedral.runtime._detect_other_fullscreen_windows",
            return_value=([{"window_id": "0x2400012", "title": "\"DALI Mirror (64-bit Development SF_VULKAN_SM5) \"", "wm_class": "\"DaliMirror\", \"DaliMirror\""}], "xprop_scan"),
        ), mock.patch(
            "cathedral.runtime.GPULease.acquire", return_value=True
        ), mock.patch(
            "cathedral.runtime.GPULease.release", return_value=True
        ), mock.patch(
            "cathedral.runtime.FishTankRenderer", return_value=fake_renderer
        ):
            runtime = DaliCathedralRuntime(
                headless=False,
                require_gpu=False,
                telegram_enabled=False,
            )
        self.assertFalse(runtime.fullscreen_guard_blocked)

    def test_enter_display_mode_starts_ue5_frontend(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.display_mode_active = False
        runtime.display_mode_reason = "startup"
        runtime._activity_interaction_pulse_until = 0.0
        runtime._last_display_transition_ts = 0.0
        runtime.idle_triggered = False
        runtime.idle_triggered_at = ""
        runtime.idle_inhibit_enabled = False
        runtime.inhibit_active = False
        runtime.inhibitor_backend = "none"
        runtime.inhibitor_backends = []
        runtime.manual_override_mode = "none"
        runtime.schedule_allowed = True
        runtime._runtime_instance_id = mock.Mock(return_value="runtime-test")
        runtime._runtime_pid = mock.Mock(return_value=1234)
        runtime._startup_force_display_mode = False
        runtime.frontend = "ue5"
        runtime._start_frontend = mock.Mock()
        runtime.log = mock.Mock()
        runtime._enter_display_mode(reason="unit_test")
        runtime._start_frontend.assert_called_once()

    def test_auto_mode_drops_display_when_ue5_frontend_unavailable(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.stop_event = mock.Mock()
        runtime.stop_event.is_set = mock.Mock(side_effect=[False, True])
        runtime._install_signal_handlers = mock.Mock()
        runtime._start_background_threads = mock.Mock()
        runtime._renew_gpu_lease = mock.Mock()
        runtime._evaluate_display_mode_state = mock.Mock()
        runtime._compute_activity_snapshot = mock.Mock()
        runtime._sync_frontend_state = mock.Mock()
        runtime._resolve_loop_rate_hz = mock.Mock(return_value=(30.0, "base"))
        runtime._refresh_renderer_runtime_context = mock.Mock()
        runtime._inference_active = mock.Mock(return_value=False)
        runtime._runtime_instance_id = mock.Mock(return_value="runtime-test")
        runtime._runtime_pid = mock.Mock(return_value=1234)
        runtime._sample_runtime_inputs = mock.Mock(return_value=({}, {}))
        runtime._stop_display_inhibitor = mock.Mock()
        runtime._stop_frontend = mock.Mock()
        runtime._unquiesce_inference_mode = mock.Mock()
        runtime._stop_background_threads = mock.Mock()
        runtime._start_frontend = mock.Mock()
        runtime.log = mock.Mock()
        runtime.frontend = "ue5"
        runtime.display_mode_active = True
        runtime.frontend_process_running = False
        runtime.manual_override_mode = "none"
        runtime.schedule_allowed = True
        runtime.idle_triggered = True
        runtime.display_mode_reason = "schedule_idle"
        runtime._display_enter_monotonic = 0.0
        runtime._last_display_transition_ts = 0.0
        runtime._display_attach_ok_logged = False
        runtime._display_attach_fail_logged = False
        runtime.loop_rate_target_hz = 0.0
        runtime.loop_rate_source = ""
        runtime.loop_sleep_ms = 0.0
        runtime.rate_limited = False
        runtime.rate_hz = 30.0
        runtime.display_rate_hz = 120.0
        runtime.display_rate_mode = "monitor"
        runtime._fatal_error = None
        runtime._lease_acquired = False
        runtime.gpu_lease = mock.Mock()
        runtime.lease_owner = "unit-test"
        runtime.renderer = mock.Mock()
        runtime.renderer.active_renderer_id = "ue5_dali_mirror"
        runtime.renderer.headless = True
        runtime.renderer.require_gpu = False
        runtime.renderer.update_signals = mock.Mock()
        runtime.renderer.set_inference_active = mock.Mock()
        runtime.renderer.present_idle_frame = mock.Mock()
        runtime.renderer.capture_state = mock.Mock(return_value={})
        runtime.renderer.frame_index = 0
        runtime._check_display_attach_state = mock.Mock()
        runtime._state_payload = mock.Mock(return_value={})
        with mock.patch("cathedral.runtime.time.monotonic", side_effect=[10.0, 10.0, 10.0, 10.0]), \
             mock.patch("cathedral.runtime.atomic_write_json"), \
             mock.patch("cathedral.runtime.time.sleep"):
            runtime.run()
        self.assertFalse(runtime.display_mode_active)
        runtime._stop_display_inhibitor.assert_called_once()
        runtime._start_frontend.assert_not_called()
        runtime.log.log.assert_any_call(
            "DISPLAY_MODE_EXIT",
            reason="frontend_unavailable",
            manual_override_mode="none",
            schedule_allowed=True,
            idle_triggered=True,
            runtime_instance_id="runtime-test",
            pid=1234,
        )


if __name__ == "__main__":
    unittest.main()
