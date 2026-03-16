import unittest
from unittest import mock
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime
from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralWorkMode(unittest.TestCase):
    def test_work_mode_accepts_therapeutic_bilateral_scene(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DALI_FISHTANK_PRESET": "work_mode_consciousness_mirror",
                "DALI_FISHTANK_WORK_SCENE": "therapeutic_bilateral",
                "DALI_FISHTANK_RENDERER_GPU_BACKEND": "0",
            },
            clear=False,
        ), mock.patch.object(
            FishTankRenderer,
            "_init_particle_state",
        ), mock.patch.object(
            FishTankRenderer,
            "_init_gpu_backend",
        ):
            renderer = FishTankRenderer(headless=True, require_gpu=False)

        self.assertTrue(renderer.work_mode_enabled)
        self.assertEqual(renderer._work_scene, "therapeutic_bilateral")

    def test_work_python_frontend_allows_visible_attach_without_gpu_backend(self):
        fake_renderer = mock.Mock()
        fake_renderer.set_runtime_context = mock.Mock()
        fake_renderer.headless = True
        fake_renderer.active_renderer_id = "renderer:test"

        with mock.patch.dict(
            "os.environ",
            {
                "DALI_FISHTANK_FRONTEND": "python",
                "DALI_FISHTANK_RENDERER_GPU_BACKEND": "0",
                "DALI_FISHTANK_IDLE_ENABLE": "0",
                "DALI_FISHTANK_ALLOW_PYTHON_VISIBLE_ATTACH": "1",
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

        self.assertEqual(runtime.frontend, "python")
        self.assertFalse(renderer_cls.call_args.kwargs["headless"])
        self.assertFalse(renderer_cls.call_args.kwargs["allow_gpu_backend"])
        self.assertFalse(renderer_cls.call_args.kwargs["require_gpu"])
        self.assertTrue(renderer_cls.call_args.kwargs["allow_visible_attach"])

    def test_runtime_state_marks_visible_python_activation(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.display_mode_active = True
        runtime.requested_mode = "on"
        runtime.effective_mode = "on"
        runtime.control_source_runtime = "agent"
        runtime.last_control_ts_runtime = "2026-03-10T09:00:00Z"
        runtime.last_control_reason_runtime = "set_mode:on"
        runtime.frontend = "python"
        runtime.frontend_process_running = False
        runtime.frontend_process_pid = 0
        runtime.frontend_process_path = ""
        runtime.frontend_last_start_ts = ""
        runtime.frontend_last_exit_code = None
        runtime.frontend_last_exit_ts = ""
        runtime.frontend_last_runtime_s = 0.0
        runtime.frontend_failure_streak = 0
        runtime.frontend_restart_backoff_s = 0.0
        runtime.frontend_next_restart_monotonic = 0.0
        runtime.frontend_launch_env_summary = {}
        runtime.frontend_run_mode = "none"
        runtime.frontend_last_status = "idle"
        runtime.frontend_last_error = ""
        runtime.frontend_last_manifest_path = ""
        runtime.frontend_last_output_root = ""
        runtime.frontend_last_completed_ts = ""
        runtime.frontend_status_path = ""
        runtime.runtime_instance_id = "cathedral-test"
        runtime.pid = 123
        runtime.runtime_start_ts = "2026-03-10T08:59:00Z"
        runtime.last_idle_activation_ts = ""
        runtime.last_control_apply_ts = ""
        runtime.last_display_attach_ts = ""
        runtime.last_display_detach_ts = ""
        runtime.schedule_enabled = False
        runtime.schedule_allowed = False
        runtime.schedule_latch_display = False
        runtime.schedule_window_start = ""
        runtime.schedule_window_end = ""
        runtime.schedule_timezone = ""
        runtime.idle_enabled = False
        runtime.idle_mode_enabled = False
        runtime.idle_seconds = 0.0
        runtime.idle_supported = False
        runtime.idle_threshold_seconds = 0.0
        runtime.idle_last_check_ok = True
        runtime.idle_last_error = ""
        runtime.idle_source = ""
        runtime.session_idle_supported = False
        runtime.session_idle_seconds = 0.0
        runtime.idle_last_input_ts = ""
        runtime.idle_reason = ""
        runtime.idle_triggered = False
        runtime.idle_trigger_source = ""
        runtime.idle_triggered_at = ""
        runtime.manual_override_mode = "on"
        runtime.inhibit_active = False
        runtime.inhibit_reason = ""
        runtime.idle_inhibit_enabled = False
        runtime.display_inhibitor_active = False
        runtime.inhibitor_backend = "none"
        runtime.display_blank_inhibit_active = False
        runtime.screensaver_inhibit_active = False
        runtime.session_inhibit_active = False
        runtime.dpms_override_active = False
        runtime.lease_owner = "lease:test"
        runtime.rate_hz = 30.0
        runtime.display_rate_hz = 0.0
        runtime.display_rate_mode = ""
        runtime.loop_rate_target_hz = 0.0
        runtime.loop_rate_source = ""
        runtime.loop_sleep_ms = 0.0
        runtime.rate_limited = False
        runtime.activity_signal = 0.0
        runtime.agent_activity_level = 0.0
        runtime.agent_count_active = 0
        runtime.coordination_density = 0.0
        runtime.routing_activity = 0.0
        runtime.interaction_activity = 0.0
        runtime.memory_activity = 0.0
        runtime.heavy_inference_suppressed = False
        runtime.semantic_activity_source_summary = ""
        runtime._sync_frontend_state = mock.Mock()

        payload = DaliCathedralRuntime._runtime_state_fields(runtime)

        self.assertEqual(payload["frontend"], "python")
        self.assertEqual(payload["effective_activation_source"], "renderer_python")
        self.assertTrue(payload["display_mode_active"])

    def test_runtime_state_respects_renderer_visibility_false(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.frontend = "python"
        runtime.frontend_fullscreen_requested = False
        runtime.display_mode_active = True
        runtime.renderer = mock.Mock()
        runtime.renderer.headless = False
        runtime.renderer.backend = "none"
        runtime._runtime_state_fields = mock.Mock(return_value={})

        payload = DaliCathedralRuntime._state_payload(
            runtime,
            {
                "backend": "none",
                "window_visible": False,
                "display_attached": False,
            },
        )

        self.assertFalse(payload["window_visible"])
        self.assertFalse(payload["display_attached"])

    def test_work_mode_can_create_tk_software_backend(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.work_mode_enabled = True
        renderer._work_grid_shape = (8, 12)
        renderer.allow_visible_attach = True
        renderer.headless = False
        renderer.backend = "none"
        renderer.gpu_mode = False
        renderer.log = mock.Mock()
        renderer._software_window = None
        renderer._software_canvas = None
        renderer._software_window_closed = False
        renderer._software_cell_size = 0

        fake_root = mock.Mock()
        fake_canvas = mock.Mock()
        fake_root.winfo_screenwidth.return_value = 1920
        fake_root.winfo_screenheight.return_value = 1080

        with mock.patch("cathedral.fishtank_renderer.tk") as fake_tk:
            fake_tk.Tk.return_value = fake_root
            fake_tk.Canvas.return_value = fake_canvas

            FishTankRenderer._init_software_backend(renderer)

        self.assertEqual(renderer.backend, "tk-work-window")
        self.assertFalse(renderer.gpu_mode)
        self.assertIs(renderer._software_window, fake_root)
        self.assertIs(renderer._software_canvas, fake_canvas)

    def test_work_mode_initializes_sparse_seeded_grid(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.work_mode_enabled = True
        renderer._work_grid_shape = (40, 60)
        renderer._work_seed_clusters = 3
        renderer.agent_count = 4096

        with mock.patch.dict(
            "os.environ",
            {
                "DALI_FISHTANK_WORK_CA_DENSITY": "0.012",
                "DALI_FISHTANK_WORK_SEED_RADIUS": "3",
            },
            clear=False,
        ):
            FishTankRenderer._init_work_mode_state(renderer)

        alive_ratio = float(renderer._work_ca_grid.mean())
        self.assertGreater(alive_ratio, 0.0)
        self.assertLess(alive_ratio, 0.08)

    def test_work_mode_preview_rows_are_emitted(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest("numpy unavailable")
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.work_mode_enabled = True
        renderer._work_ca_grid = [
            [1, 0, 1, 0],
            [0, 1, 0, 1],
        ]

        renderer._work_ca_grid = np.array(renderer._work_ca_grid, dtype="uint8")
        preview = FishTankRenderer._work_mode_preview_rows(renderer, max_rows=4, max_cols=4)

        self.assertEqual(preview, ["#.#.", ".#.#"])

    def test_work_mode_can_render_fantasy_landscape_scene(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._fantasy_scene_state = {}
        renderer._fantasy_scene_dimensions = (0, 0)
        renderer._fantasy_scene_started_ts = 0.0
        renderer._work_scene_time_scale = 0.28
        renderer._work_growth_memory = 0.01
        renderer.control_values = {"curiosity_impulse": 0.2}
        renderer.signals = mock.Mock(gpu_util=0.12)

        canvas = mock.Mock()

        FishTankRenderer._render_fantasy_landscape_scene(renderer, canvas, 1280, 720, 10.0)

        self.assertTrue(canvas.create_polygon.called)
        self.assertTrue(canvas.create_oval.called)
        self.assertEqual(renderer._fantasy_scene_dimensions, (1280, 720))
        self.assertEqual(len(renderer._fantasy_scene_state.get("clouds", [])), 4)
        self.assertEqual(len(renderer._fantasy_scene_state.get("mist_bands", [])), 5)
        self.assertEqual(len(renderer._fantasy_scene_state.get("ducks", [])), 4)
        self.assertEqual(len(renderer._fantasy_scene_state.get("fish", [])), 7)
        self.assertIn("dragon", renderer._fantasy_scene_state)

    def test_work_mode_can_render_therapeutic_bilateral_scene(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._therapeutic_scene_state = {}
        renderer._therapeutic_scene_dimensions = (0, 0)
        renderer._therapeutic_scene_started_ts = 0.0
        renderer._work_scene_time_scale = 0.28
        renderer._therapeutic_inhale_seconds = 4.0
        renderer._therapeutic_hold_seconds = 2.0
        renderer._therapeutic_exhale_seconds = 5.0
        renderer._therapeutic_breath_seconds = 11.0
        renderer._therapeutic_sweep_seconds = 7.5
        renderer._therapeutic_settle_seconds = 4.0
        renderer._therapeutic_prompt_interval_s = 24.0
        renderer._therapeutic_motion_gain = 0.7
        renderer._therapeutic_drift_seconds = 180.0
        renderer._therapeutic_drift_ratio = 0.01
        renderer._therapeutic_text_timeout_s = 60.0
        renderer._therapeutic_grounding_enabled = True
        renderer._work_growth_memory = 0.01
        renderer.control_values = {"curiosity_impulse": 0.2}
        renderer.signals = mock.Mock(gpu_util=0.08)

        canvas = mock.Mock()

        FishTankRenderer._ensure_therapeutic_bilateral_state(renderer, 1280, 720)
        renderer._therapeutic_scene_started_ts = 0.5
        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 10.5)

        self.assertTrue(canvas.create_line.called)
        self.assertTrue(canvas.create_oval.called)
        self.assertTrue(canvas.create_text.called)
        self.assertEqual(renderer._therapeutic_scene_dimensions, (1280, 720))
        self.assertEqual(len(renderer._therapeutic_scene_state.get("stars", [])), 42)
        self.assertEqual(len(renderer._therapeutic_scene_state.get("ribbons", [])), 4)
        self.assertEqual(len(renderer._therapeutic_scene_state.get("grounding_cues", [])), 5)
        self.assertEqual(renderer._therapeutic_scene_state.get("current_direction"), "left_to_right")
        self.assertEqual(renderer._therapeutic_scene_state.get("current_phase"), "sweep")
        self.assertEqual(renderer._therapeutic_scene_state.get("current_breath"), "exhale")
        self.assertGreater(float(renderer._therapeutic_scene_state.get("breath_elapsed_seconds", 0.0) or 0.0), 9.0)
        self.assertLess(float(renderer._therapeutic_scene_state.get("breath_phase_progress", 1.0) or 1.0), 1.0)
        self.assertGreater(float(renderer._therapeutic_scene_state.get("orb_offset_ratio", 0.0) or 0.0), 0.85)
        self.assertTrue(renderer._therapeutic_scene_state.get("text_enabled"))
        self.assertFalse(renderer._therapeutic_scene_state.get("cue_text_visible"))
        self.assertFalse(renderer._therapeutic_scene_state.get("footer_text_visible"))
        self.assertTrue(renderer._therapeutic_scene_state.get("breath_label_visible"))
        self.assertFalse(renderer._therapeutic_scene_state.get("breath_caption_visible"))
        self.assertGreater(float(renderer._therapeutic_scene_state.get("ring_radius_px", 0.0) or 0.0), 55.0)
        self.assertLessEqual(abs(float(renderer._therapeutic_scene_state.get("drift_x_px", 0.0) or 0.0)), 12.8)
        self.assertLessEqual(abs(float(renderer._therapeutic_scene_state.get("drift_y_px", 0.0) or 0.0)), 7.2)

    def test_work_mode_therapeutic_bilateral_direction_flips_between_cycles(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._therapeutic_scene_state = {}
        renderer._therapeutic_scene_dimensions = (0, 0)
        renderer._therapeutic_scene_started_ts = 0.0
        renderer._work_scene_time_scale = 0.28
        renderer._therapeutic_inhale_seconds = 4.0
        renderer._therapeutic_hold_seconds = 2.0
        renderer._therapeutic_exhale_seconds = 5.0
        renderer._therapeutic_breath_seconds = 11.0
        renderer._therapeutic_sweep_seconds = 7.5
        renderer._therapeutic_settle_seconds = 4.0
        renderer._therapeutic_prompt_interval_s = 24.0
        renderer._therapeutic_motion_gain = 0.7
        renderer._therapeutic_drift_seconds = 180.0
        renderer._therapeutic_drift_ratio = 0.01
        renderer._therapeutic_text_timeout_s = 60.0
        renderer._therapeutic_grounding_enabled = True
        renderer._work_growth_memory = 0.01
        renderer.control_values = {"curiosity_impulse": 0.2}
        renderer.signals = mock.Mock(gpu_util=0.08)
        canvas = mock.Mock()

        FishTankRenderer._ensure_therapeutic_bilateral_state(renderer, 1280, 720)
        renderer._therapeutic_scene_started_ts = 0.5
        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 3.5)
        self.assertEqual(renderer._therapeutic_scene_state.get("current_phase"), "sweep")
        self.assertEqual(renderer._therapeutic_scene_state.get("current_direction"), "left_to_right")
        self.assertTrue(renderer._therapeutic_scene_state.get("cue_text_visible"))
        self.assertTrue(renderer._therapeutic_scene_state.get("footer_text_visible"))

        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 13.5)
        self.assertEqual(renderer._therapeutic_scene_state.get("current_phase"), "sweep")
        self.assertEqual(renderer._therapeutic_scene_state.get("current_direction"), "right_to_left")
        self.assertFalse(renderer._therapeutic_scene_state.get("cue_text_visible"))
        self.assertFalse(renderer._therapeutic_scene_state.get("footer_text_visible"))

    def test_work_mode_therapeutic_bilateral_reverses_without_center_reset(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._therapeutic_scene_state = {}
        renderer._therapeutic_scene_dimensions = (0, 0)
        renderer._therapeutic_scene_started_ts = 0.0
        renderer._work_scene_time_scale = 0.28
        renderer._therapeutic_inhale_seconds = 4.0
        renderer._therapeutic_hold_seconds = 2.0
        renderer._therapeutic_exhale_seconds = 5.0
        renderer._therapeutic_breath_seconds = 11.0
        renderer._therapeutic_sweep_seconds = 7.5
        renderer._therapeutic_settle_seconds = 4.0
        renderer._therapeutic_prompt_interval_s = 24.0
        renderer._therapeutic_motion_gain = 0.7
        renderer._therapeutic_drift_seconds = 180.0
        renderer._therapeutic_drift_ratio = 0.01
        renderer._therapeutic_text_timeout_s = 60.0
        renderer._therapeutic_grounding_enabled = True
        renderer._work_growth_memory = 0.01
        renderer.control_values = {"curiosity_impulse": 0.2}
        renderer.signals = mock.Mock(gpu_util=0.08)
        canvas = mock.Mock()

        FishTankRenderer._ensure_therapeutic_bilateral_state(renderer, 1280, 720)
        renderer._therapeutic_scene_started_ts = 0.5

        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 11.9)
        before_ratio = float(renderer._therapeutic_scene_state.get("orb_offset_ratio", 0.0) or 0.0)
        before_dir = renderer._therapeutic_scene_state.get("current_direction")

        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 12.1)
        after_ratio = float(renderer._therapeutic_scene_state.get("orb_offset_ratio", 0.0) or 0.0)
        after_dir = renderer._therapeutic_scene_state.get("current_direction")

        self.assertGreater(before_ratio, 0.95)
        self.assertGreater(after_ratio, 0.95)
        self.assertEqual(before_dir, "left_to_right")
        self.assertEqual(after_dir, "right_to_left")

    def test_work_mode_therapeutic_bilateral_hides_all_text_after_timeout(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._therapeutic_scene_state = {}
        renderer._therapeutic_scene_dimensions = (0, 0)
        renderer._therapeutic_scene_started_ts = 0.0
        renderer._work_scene_time_scale = 0.28
        renderer._therapeutic_inhale_seconds = 4.0
        renderer._therapeutic_hold_seconds = 2.0
        renderer._therapeutic_exhale_seconds = 5.0
        renderer._therapeutic_breath_seconds = 11.0
        renderer._therapeutic_sweep_seconds = 7.5
        renderer._therapeutic_settle_seconds = 4.0
        renderer._therapeutic_prompt_interval_s = 24.0
        renderer._therapeutic_motion_gain = 0.7
        renderer._therapeutic_drift_seconds = 180.0
        renderer._therapeutic_drift_ratio = 0.01
        renderer._therapeutic_text_timeout_s = 60.0
        renderer._therapeutic_grounding_enabled = True
        renderer._work_growth_memory = 0.01
        renderer.control_values = {"curiosity_impulse": 0.2}
        renderer.signals = mock.Mock(gpu_util=0.08)
        canvas = mock.Mock()

        FishTankRenderer._ensure_therapeutic_bilateral_state(renderer, 1280, 720)
        renderer._therapeutic_scene_started_ts = 0.5
        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 61.0)

        self.assertFalse(renderer._therapeutic_scene_state.get("text_enabled"))
        self.assertFalse(renderer._therapeutic_scene_state.get("cue_text_visible"))
        self.assertFalse(renderer._therapeutic_scene_state.get("footer_text_visible"))
        self.assertFalse(renderer._therapeutic_scene_state.get("breath_label_visible"))
        self.assertFalse(renderer._therapeutic_scene_state.get("breath_caption_visible"))

    def test_work_mode_therapeutic_breath_timing_hits_4_2_5_segments(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._therapeutic_scene_state = {}
        renderer._therapeutic_scene_dimensions = (0, 0)
        renderer._therapeutic_scene_started_ts = 0.0
        renderer._work_scene_time_scale = 0.28
        renderer._therapeutic_inhale_seconds = 4.0
        renderer._therapeutic_hold_seconds = 2.0
        renderer._therapeutic_exhale_seconds = 5.0
        renderer._therapeutic_breath_seconds = 11.0
        renderer._therapeutic_sweep_seconds = 7.5
        renderer._therapeutic_settle_seconds = 4.0
        renderer._therapeutic_prompt_interval_s = 24.0
        renderer._therapeutic_motion_gain = 0.7
        renderer._therapeutic_drift_seconds = 180.0
        renderer._therapeutic_drift_ratio = 0.01
        renderer._therapeutic_text_timeout_s = 60.0
        renderer._therapeutic_grounding_enabled = True
        renderer._work_growth_memory = 0.01
        renderer.control_values = {"curiosity_impulse": 0.2}
        renderer.signals = mock.Mock(gpu_util=0.08)
        canvas = mock.Mock()

        FishTankRenderer._ensure_therapeutic_bilateral_state(renderer, 1280, 720)
        renderer._therapeutic_scene_started_ts = 0.5

        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 3.5)
        self.assertEqual(renderer._therapeutic_scene_state.get("current_breath"), "inhale")
        inhale_radius = float(renderer._therapeutic_scene_state.get("ring_radius_px", 0.0) or 0.0)

        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 5.0)
        self.assertEqual(renderer._therapeutic_scene_state.get("current_breath"), "hold")
        hold_radius = float(renderer._therapeutic_scene_state.get("ring_radius_px", 0.0) or 0.0)

        FishTankRenderer._render_therapeutic_bilateral_scene(renderer, canvas, 1280, 720, 9.0)
        self.assertEqual(renderer._therapeutic_scene_state.get("current_breath"), "exhale")
        exhale_radius = float(renderer._therapeutic_scene_state.get("ring_radius_px", 0.0) or 0.0)

        self.assertLess(inhale_radius, hold_radius)
        self.assertLess(exhale_radius, hold_radius)


if __name__ == "__main__":
    unittest.main()
