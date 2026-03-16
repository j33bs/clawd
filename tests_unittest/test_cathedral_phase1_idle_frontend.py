import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime


class TestCathedralPhase1IdleFrontend(unittest.TestCase):
    def test_phase1_frontend_keeps_python_renderer_visible(self):
        fake_renderer = mock.Mock()
        fake_renderer.set_runtime_context = mock.Mock()
        fake_renderer.headless = False
        fake_renderer.active_renderer_id = "renderer:test"

        with mock.patch.dict(
            "os.environ",
            {
                "DALI_FISHTANK_FRONTEND": "phase1",
                "DALI_FISHTANK_IDLE_ENABLE": "1",
            },
            clear=False,
        ), mock.patch(
            "cathedral.runtime.GPULease.acquire",
            return_value=True,
        ), mock.patch(
            "cathedral.runtime.GPULease.release",
            return_value=True,
        ), mock.patch.object(
            DaliCathedralRuntime,
            "_quiesce_inference_mode",
            return_value=None,
        ), mock.patch.object(
            DaliCathedralRuntime,
            "_unquiesce_inference_mode",
            return_value=None,
        ), mock.patch.object(
            DaliCathedralRuntime,
            "_warn_if_headless_without_consumer",
            return_value=None,
        ), mock.patch(
            "cathedral.runtime.FishTankRenderer",
            return_value=fake_renderer,
        ) as renderer_cls:
            runtime = DaliCathedralRuntime(
                headless=False,
                require_gpu=False,
                telegram_enabled=False,
            )

        self.assertEqual(runtime.frontend, "phase1")
        self.assertFalse(renderer_cls.call_args.kwargs["headless"])
        self.assertTrue(renderer_cls.call_args.kwargs["allow_gpu_backend"])

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
        runtime.renderer = mock.Mock()
        runtime.renderer.headless = True
        runtime.log = mock.Mock()

        DaliCathedralRuntime._handle_phase1_frontend_completion(runtime)

        runtime._exit_display_mode.assert_called_once_with(reason="phase1_complete")

    def test_phase1_frontend_completion_keeps_preview_visible_when_renderer_is_windowed(self):
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
        runtime.renderer = mock.Mock()
        runtime.renderer.headless = False
        runtime.log = mock.Mock()

        DaliCathedralRuntime._handle_phase1_frontend_completion(runtime)

        runtime._exit_display_mode.assert_not_called()

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

    def test_phase1_stop_writes_terminated_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            status_path = Path(tmpdir) / "phase1_idle_status.json"
            runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
            runtime.frontend = "phase1"
            runtime.frontend_status_path = str(status_path)
            runtime.frontend_last_status_payload = {
                "schema_version": "dali.phase1.idle-status.v1",
                "status": "running",
                "output_root": str(Path(tmpdir) / "output"),
            }
            runtime.frontend_last_status = "running"
            runtime.frontend_last_error = ""
            runtime.frontend_last_manifest_path = ""
            runtime.frontend_last_output_root = str(Path(tmpdir) / "output")
            runtime.frontend_last_completed_ts = ""
            runtime.frontend_last_exit_code = None
            runtime.frontend_process_path = "/tmp/dali_phase1_idle_run.sh"
            runtime.frontend_process_running = True
            runtime.frontend_process_pid = 4242
            runtime.frontend_activation_pending = True
            runtime.frontend_process = mock.Mock()
            runtime.frontend_process.poll.return_value = None
            runtime.frontend_process.wait.return_value = 143
            runtime._frontend_log_handle = None
            runtime.log = mock.Mock()

            DaliCathedralRuntime._stop_frontend(runtime)

            payload = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "terminated")
        self.assertEqual(int(payload["exit_code"]), 143)
        self.assertEqual(runtime.frontend_last_status, "terminated")
        self.assertFalse(runtime.frontend_process_running)

    def test_idle_resume_exits_auto_display_mode(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.idle_mode_enabled = True
        runtime.frontend = "phase1"
        runtime.phase1_idle_autorun_enabled = True
        runtime.display_mode_active = True
        runtime.requested_mode = "auto"
        runtime.display_mode_reason = "internal_idle"
        runtime.idle_trigger_source = "internal"
        runtime.idle_seconds = 300.0
        runtime._manual_enter_display_mode = False
        runtime._phase1_idle_episode_consumed = True
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 0.0))
        runtime._exit_display_mode = mock.Mock()
        runtime.log = mock.Mock()
        runtime._last_idle_wait_log_ts = 0.0
        runtime._phase1_idle_autorun_block_log_ts = 0.0

        DaliCathedralRuntime._update_idle_display_state(runtime)

        runtime._exit_display_mode.assert_called_once_with(reason="idle_resumed")
        self.assertFalse(runtime._phase1_idle_episode_consumed)

    def test_phase1_idle_autorun_is_blocked_by_default(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.idle_mode_enabled = True
        runtime.frontend = "phase1"
        runtime.phase1_idle_autorun_enabled = False
        runtime.display_mode_active = False
        runtime.requested_mode = "auto"
        runtime.display_mode_reason = ""
        runtime.idle_trigger_source = "session"
        runtime.idle_seconds = 30.0
        runtime._manual_enter_display_mode = False
        runtime._phase1_idle_episode_consumed = False
        runtime._probe_session_idle_seconds = mock.Mock(return_value=(True, 45.0))
        runtime._enter_display_mode = mock.Mock()
        runtime.log = mock.Mock()
        runtime._last_idle_wait_log_ts = 0.0
        runtime._phase1_idle_autorun_block_log_ts = 0.0

        DaliCathedralRuntime._update_idle_display_state(runtime)

        runtime._enter_display_mode.assert_not_called()
        runtime.log.log.assert_any_call(
            "phase1_idle_autorun_blocked",
            reason="phase1_offline_generation_is_manual_only",
            idle_seconds=30.0,
            idle_observed=45.0,
        )

    def test_phase1_state_payload_marks_fullscreen_preview_visible(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.frontend = "phase1"
        runtime.frontend_fullscreen_requested = True
        runtime.display_mode_active = True
        runtime.renderer = mock.Mock()
        runtime.renderer.headless = False
        runtime.renderer.backend = "glfw-fullscreen"
        runtime._runtime_state_fields = mock.Mock(return_value={})

        payload = DaliCathedralRuntime._state_payload(runtime, {"backend": "glfw-fullscreen"})

        self.assertTrue(payload["window_visible"])
        self.assertTrue(payload["display_attached"])
        self.assertTrue(payload["fullscreen_attached"])
        self.assertTrue(payload["monitor_bound"])


if __name__ == "__main__":
    unittest.main()
