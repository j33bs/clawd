import os
import json
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer
from cathedral.runtime import DaliCathedralRuntime


class TestCathedralIdlePaletteContract(unittest.TestCase):
    def test_palette_modes_present_and_default_dusk(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.palette_mode = "dusk"
        renderer._ctx = None
        self.assertEqual(renderer._palette_mode_index(), 0)
        for mode in ("dusk", "aurora", "roseglass", "ember", "mono", "dali"):
            self.assertTrue(renderer.set_palette_mode(mode))
        self.assertFalse(renderer.set_palette_mode("heatmap"))

    def test_identity_profile_default_dali(self):
        with mock.patch.dict("os.environ", {"DALI_FISHTANK_IDENTITY_PROFILE": "dali"}, clear=False), mock.patch.object(
            FishTankRenderer, "_init_particle_state"
        ), mock.patch.object(FishTankRenderer, "_init_gpu_backend"):
            renderer = FishTankRenderer(headless=True, require_gpu=False)
        self.assertEqual(renderer.identity_profile, "dali")
        self.assertEqual(renderer.profile_palette_family, "dali_soft_cathedral")
        self.assertEqual(renderer.palette_mode, "dali")

    def test_dali_profile_weights_contract(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.identity_profile = "neutral"
        renderer.profile_palette_family = "neutral"
        renderer.palette_mode = "dusk"
        renderer.motif_weights = {}
        renderer.exposure_base = 1.4
        renderer.bloom_strength = 0.4
        renderer.contrast_base = 1.0
        renderer.saturation_base = 1.0
        renderer.white_balance = (1.0, 1.0, 1.0)
        renderer.layer_weight_particles = 0.5
        renderer.layer_weight_rd = 1.0
        renderer.layer_weight_volume = 1.0
        renderer.temporal_alpha_base = 0.9
        renderer.shader_params = {}
        self.assertTrue(renderer.set_identity_profile("dali"))
        self.assertEqual(renderer.identity_profile, "dali")
        self.assertEqual(renderer.profile_palette_family, "dali_soft_cathedral")
        self.assertEqual(renderer.palette_mode, "dali")
        self.assertGreater(renderer.layer_weight_volume, renderer.layer_weight_particles)
        self.assertGreater(renderer.layer_weight_rd, 1.0)

    def test_temporal_reset_on_palette_change(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.palette_mode = "dusk"
        renderer._ctx = None
        renderer._pending_history_reset_reason = ""
        self.assertTrue(renderer.set_palette_mode("aurora"))
        self.assertEqual(renderer.last_temporal_reset_reason, "palette_change")
        self.assertEqual(renderer._pending_history_reset_reason, "palette_change")

    def test_debug_view_mode_normalization(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.debug_view_mode = "final"
        self.assertTrue(renderer.set_debug_view_mode("channel_b"))
        self.assertEqual(renderer.debug_view_mode, "channel_b")
        self.assertTrue(renderer.set_debug_view_mode("not_a_mode"))
        self.assertEqual(renderer.debug_view_mode, "final")

    def test_idle_state_fields_present(self):
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.lease_mode = "exclusive"
        renderer.inference_quiesced = False
        renderer.schedule_enabled = False
        renderer.schedule_allowed = False
        renderer.schedule_window_start = "17:00"
        renderer.schedule_window_end = "21:00"
        renderer.idle_enabled = False
        renderer.idle_mode_enabled = False
        renderer.idle_triggered = False
        renderer.idle_trigger_source = "internal"
        renderer.idle_triggered_at = ""
        renderer.manual_override_mode = "none"
        renderer.display_mode_active = False
        renderer.display_mode_reason = "startup"
        renderer.inhibit_active = False
        renderer.display_inhibitor_active = False
        renderer.inhibitor_backend = "none"
        renderer.inhibitor_backends = []
        renderer.display_blank_inhibit_active = False
        renderer.screensaver_inhibit_active = False
        renderer.session_inhibit_active = False
        renderer.dpms_override_active = False
        renderer._window = None
        renderer._window_visible = False
        renderer.set_runtime_context(
            lease_mode="shared",
            inference_quiesced=True,
            schedule_enabled=True,
            schedule_allowed=True,
            schedule_window_start="17:00",
            schedule_window_end="21:00",
            idle_enabled=True,
            idle_mode_enabled=True,
            idle_triggered=True,
            idle_trigger_source="manual",
            idle_triggered_at="2026-03-06T00:00:00Z",
            manual_override_mode="on",
            display_mode_active=True,
            display_mode_reason="manual_on",
            inhibit_active=True,
            display_inhibitor_active=True,
            inhibitor_backend="systemd-inhibit-child",
            inhibitor_backends=["systemd-inhibit-child", "dbus-screensaver", "x11-dpms"],
            display_blank_inhibit_active=True,
            screensaver_inhibit_active=True,
            session_inhibit_active=False,
            dpms_override_active=True,
        )
        self.assertEqual(renderer.lease_mode, "shared")
        self.assertTrue(renderer.inference_quiesced)
        self.assertTrue(renderer.schedule_enabled)
        self.assertTrue(renderer.schedule_allowed)
        self.assertEqual(renderer.schedule_window_start, "17:00")
        self.assertEqual(renderer.schedule_window_end, "21:00")
        self.assertTrue(renderer.idle_enabled)
        self.assertTrue(renderer.idle_mode_enabled)
        self.assertTrue(renderer.idle_triggered)
        self.assertEqual(renderer.idle_trigger_source, "manual")
        self.assertEqual(renderer.manual_override_mode, "on")
        self.assertTrue(renderer.display_mode_active)
        self.assertEqual(renderer.display_mode_reason, "manual_on")
        self.assertTrue(renderer.inhibit_active)
        self.assertTrue(renderer.display_inhibitor_active)
        self.assertEqual(renderer.inhibitor_backend, "systemd-inhibit-child")
        self.assertEqual(renderer.inhibitor_backends, ["systemd-inhibit-child", "dbus-screensaver", "x11-dpms"])
        self.assertTrue(renderer.display_blank_inhibit_active)
        self.assertTrue(renderer.screensaver_inhibit_active)
        self.assertFalse(renderer.session_inhibit_active)
        self.assertTrue(renderer.dpms_override_active)

    def test_inhibitor_flag_transitions(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.log = mock.Mock()
        runtime.manual_override_mode = "none"
        runtime.schedule_allowed = True
        runtime.idle_triggered = True
        runtime.idle_trigger_source = "internal"
        runtime.idle_seconds = 300.0
        runtime.requested_mode = "auto"
        runtime.effective_activation_source = "none"
        runtime._current_idle_seconds = 0.0
        runtime.idle_inhibit_enabled = True
        runtime.display_mode_active = False
        runtime.display_mode_reason = "startup"
        runtime.inhibit_active = False
        runtime.display_inhibitor_active = False
        runtime.inhibitor_backend = "none"
        runtime.idle_triggered_at = ""
        runtime._last_display_transition_ts = 0.0
        runtime._startup_force_display_mode = False
        runtime._start_display_inhibitor = mock.Mock(
            side_effect=lambda: (
                setattr(runtime, "display_inhibitor_active", True),
                setattr(runtime, "inhibit_active", True),
            )
        )
        runtime._stop_display_inhibitor = mock.Mock(
            side_effect=lambda: (
                setattr(runtime, "display_inhibitor_active", False),
                setattr(runtime, "inhibit_active", False),
            )
        )
        runtime._enter_display_mode(reason="unit_test")
        self.assertTrue(runtime.display_mode_active)
        self.assertTrue(runtime.inhibit_active)
        self.assertTrue(runtime.display_inhibitor_active)
        runtime._exit_display_mode(reason="unit_test_done")
        self.assertFalse(runtime.display_mode_active)
        self.assertFalse(runtime.inhibit_active)
        self.assertFalse(runtime.display_inhibitor_active)

    def test_tg_missing_env_warn_only_when_not_required(self):
        script = (REPO_ROOT / "tools" / "verify_dali_fishtank_live.sh").read_text(encoding="utf-8")
        self.assertIn("DALI_FISHTANK_TELEGRAM_REQUIRED", script)
        self.assertIn("telegram_enabled_but_missing_env_optional", script)

    def test_start_script_defaults_to_scheduled_mode(self):
        script = (REPO_ROOT / "scripts" / "dali_fishtank_start.sh").read_text(encoding="utf-8")
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_ENABLED" "1"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_LATCH_DISPLAY" "0"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_START" "17:00"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_END" "21:00"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_TIMEZONE" "Australia/Brisbane"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_ENTER_DISPLAY_MODE" "0"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_SCHEDULE_LATCH_DISPLAY" "0"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_DISPLAY_RATE_MODE" "monitor"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_DISPLAY_RATE_HZ" "120"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_FRONTEND" "phase1"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_UE5_LAUNCHER" "$ROOT_DIR/workspace/dali_unreal/Saved/StagedBuilds/Linux/DaliMirror.sh"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_PHASE1_LAUNCHER" "$ROOT_DIR/scripts/dali_phase1_idle_run.sh"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_PHASE1_STATUS_PATH" "$ROOT_DIR/workspace/runtime/phase1_idle_status.json"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_SWAP_INTERVAL" "1"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_PRESENT_EXPERIMENT" "off"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_PRESENT_RATE_CAP_OVERRIDE_HZ" "0"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_ABORT_IF_FULLSCREEN_ACTIVE" "1"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_IDLE_SECONDS" "180"', script)
        self.assertIn("migrate_legacy_frontend_defaults", script)

    def test_cathedralctl_work_profile_uses_visible_software_scene(self):
        script = (REPO_ROOT / "tools" / "cathedralctl").read_text(encoding="utf-8")
        self.assertIn('"DALI_FISHTANK_RENDERER_GPU_BACKEND": "0"', script)
        self.assertIn('"DALI_FISHTANK_ALLOW_PYTHON_VISIBLE_ATTACH": "1"', script)
        self.assertIn('"DALI_FISHTANK_WORK_SCENE": "therapeutic_bilateral"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_GROUNDING_ENABLED": "1"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_INHALE_SECONDS": "4.0"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_HOLD_SECONDS": "2.0"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_EXHALE_SECONDS": "5.0"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_DRIFT_SECONDS": "180.0"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_DRIFT_RATIO": "0.01"', script)
        self.assertIn('"DALI_FISHTANK_THERAPEUTIC_TEXT_TIMEOUT_S": "60.0"', script)

    def test_present_compare_script_exists_and_probes_swap_modes(self):
        script = (REPO_ROOT / "scripts" / "dali_present_path_compare.sh").read_text(encoding="utf-8")
        self.assertIn("DALI_FISHTANK_SWAP_INTERVAL", script)
        self.assertIn("DALI_FISHTANK_PRESENT_EXPERIMENT", script)
        self.assertIn("swap1_vsync", script)
        self.assertIn("swap0_uncapped", script)
        self.assertIn("fishtank_capture_request.json", script)

    def test_start_script_defaults_to_dali_identity(self):
        script = (REPO_ROOT / "scripts" / "dali_fishtank_start.sh").read_text(encoding="utf-8")
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_IDENTITY_PROFILE" "dali"', script)
        self.assertIn('upsert_default_if_blank "DALI_FISHTANK_PALETTE_MODE" "dali"', script)

    def test_cathedral_soft_preset_does_not_override_configured_palette(self):
        from unittest import mock

        with mock.patch.dict(
            os.environ,
            {
                "DALI_FISHTANK_PRESET": "cathedral_soft",
                "DALI_FISHTANK_PALETTE_MODE": "aurora",
            },
            clear=False,
        ), mock.patch.object(FishTankRenderer, "_init_particle_state"), mock.patch.object(
            FishTankRenderer, "_init_gpu_backend"
        ):
            renderer = FishTankRenderer(headless=True, require_gpu=False)
        self.assertEqual(renderer.palette_mode, "aurora")

    def test_capture_state_exports_semantic_fields(self):
        with mock.patch.object(FishTankRenderer, "_init_gpu_backend"):
            renderer = FishTankRenderer(headless=True, require_gpu=False)
        telemetry = {
            "gpu_temp": 48.0,
            "gpu_util": 0.55,
            "gpu_vram": 0.52,
            "gpu_vram_used_mb": 4096.0,
            "cpu_temp": 62.0,
            "fan_gpu": 1400.0,
            "disk_io": 0.18,
        }
        tacti = {
            "arousal": 0.64,
            "memory_recall_density": 0.42,
            "token_flux": 0.58,
        }
        renderer.update_signals(telemetry, tacti)
        state = renderer.capture_state()
        self.assertIn("mirror_state", state)
        self.assertIn("state_hue_mix", state)
        self.assertIn("motif_activation", state)

    def test_runtime_state_payload_marks_ue5_frontend_visible(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.frontend = "ue5"
        runtime.frontend_process_running = True
        runtime.frontend_process_pid = 4242
        runtime.frontend_process_path = "/tmp/DaliMirror.sh"
        runtime._sync_frontend_state = mock.Mock()
        runtime._runtime_state_fields = mock.Mock(return_value={"frontend": "ue5", "display_mode_active": True})
        payload = runtime._state_payload({"active_renderer_id": "python_renderer", "window_visible": False})
        self.assertEqual(payload["active_renderer_id"], "ue5_dali_mirror")
        self.assertEqual(payload["active_renderer_name"], "UE5 DaliMirror")
        self.assertEqual(payload["frontend"], "ue5")
        self.assertTrue(payload["window_visible"])
        self.assertTrue(payload["fullscreen_requested"])
        self.assertTrue(payload["fullscreen_attached"])
        self.assertTrue(payload["display_attached"])

    def test_present_loop_runtime_context_fields_round_trip(self):
        with mock.patch.object(FishTankRenderer, "_init_gpu_backend"):
            renderer = FishTankRenderer(headless=True, require_gpu=False)
        renderer.set_runtime_context(
            lease_mode="shared",
            inference_quiesced=False,
            loop_rate_target_hz=120.0,
            loop_rate_source="monitor_refresh",
            loop_sleep_ms=0.0,
            rate_limited=False,
            present_experiment_mode="swap0_probe",
        )
        state = renderer.capture_state()
        self.assertEqual(state["loop_rate_target_hz"], 120.0)
        self.assertEqual(state["loop_rate_source"], "monitor_refresh")
        self.assertEqual(state["loop_sleep_ms"], 0.0)
        self.assertFalse(state["rate_limited"])
        self.assertEqual(state["present_experiment_mode"], "swap0_probe")
        self.assertEqual(int(state["swap_interval"]), 1)


if __name__ == "__main__":
    unittest.main()
