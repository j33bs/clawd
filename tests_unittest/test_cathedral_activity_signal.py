import time
import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.runtime import DaliCathedralRuntime


class TestCathedralActivitySignal(unittest.TestCase):
    def test_compute_activity_snapshot_prefers_agent_coordination_when_suppressed(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime.control_bus = mock.Mock()
        runtime.control_bus.active_transient.return_value = {
            "curiosity_impulse": {"value": 0.9, "ttl_s": 9.0},
            "density_boost": {"value": 1.2, "ttl_s": 8.0},
            "exposure_boost": {"value": 1.5, "ttl_s": 8.0},
        }
        runtime._read_json = mock.Mock(
            return_value={
                "triggered": True,
                "ts": "2026-03-07T01:20:00Z",
            }
        )
        runtime.inference_quiesced = True
        runtime.lease_mode = "exclusive"
        runtime._activity_interaction_pulse_until = time.monotonic() + 18.0
        runtime._activity_curiosity_pulse_until = time.monotonic() + 12.0

        telemetry = {"gpu_util": 0.05, "cpu_load": 0.18}
        tacti = {
            "active_agents": ["agent-1", "agent-2", "agent-3", "agent-4"],
            "token_flux": 0.26,
            "memory_recall_density": 0.42,
            "research_depth": 0.33,
        }
        snapshot = runtime._compute_activity_snapshot(telemetry, tacti)

        self.assertTrue(snapshot["heavy_inference_suppressed"])
        self.assertGreater(snapshot["activity_signal"], 0.3)
        self.assertGreater(snapshot["agent_activity_level"], 0.35)
        self.assertGreater(snapshot["coordination_density"], 0.3)
        self.assertGreater(snapshot["routing_activity"], 0.2)
        self.assertEqual(snapshot["agent_count_active"], 4)
        summary = str(snapshot["semantic_activity_source_summary"])
        self.assertTrue(summary)
        self.assertTrue(any(label in summary for label in ("agent:", "coordination:", "routing:", "interaction:")))

    def test_runtime_state_exports_activity_fields(self):
        runtime = DaliCathedralRuntime.__new__(DaliCathedralRuntime)
        runtime._ensure_inhibitor_defaults = mock.Mock()
        runtime._sync_inhibitor_state = mock.Mock()
        runtime._read_json = mock.Mock(return_value={"owner": "dali-fishtank:test"})
        runtime.schedule_slots = []
        runtime.requested_mode = "auto"
        runtime.effective_mode = "auto"
        runtime.control_source = "unit_test"
        runtime.last_control_ts = ""
        runtime.last_control_reason = ""
        runtime.last_control_apply_ts = ""
        runtime.last_idle_activation_ts = ""
        runtime.runtime_instance_id = "cathedral-test"
        runtime.pid = 1234
        runtime.runtime_start_ts = "2026-03-07T00:00:00Z"
        runtime.schedule_enabled = True
        runtime.schedule_allowed = True
        runtime.schedule_window_start = "17:00"
        runtime.schedule_window_end = "21:00"
        runtime.schedule_timezone = "Australia/Brisbane"
        runtime.idle_enabled = True
        runtime.idle_mode_enabled = True
        runtime.idle_seconds = 42.0
        runtime.idle_supported = True
        runtime.idle_threshold_seconds = 300.0
        runtime.idle_last_check_ok = True
        runtime.idle_last_error = ""
        runtime.idle_source = "session"
        runtime.session_idle_supported = True
        runtime.session_idle_seconds = 12.0
        runtime.idle_last_input_ts = ""
        runtime.idle_reason = "mutter"
        runtime.idle_triggered = False
        runtime.idle_trigger_source = "session"
        runtime.idle_triggered_at = ""
        runtime.manual_override_mode = "none"
        runtime.display_mode_active = True
        runtime.display_mode_reason = "manual_on"
        runtime.effective_activation_source = "manual_on"
        runtime.inhibit_active = True
        runtime.inhibit_reason = "Dali Cathedral display mode"
        runtime.idle_inhibit_enabled = True
        runtime.display_inhibitor_active = True
        runtime.inhibitor_backend = "systemd-inhibit-child"
        runtime.inhibitor_backends = ["systemd-inhibit-child", "dbus-screensaver"]
        runtime.display_blank_inhibit_active = True
        runtime.screensaver_inhibit_active = True
        runtime.session_inhibit_active = False
        runtime.dpms_override_active = False
        runtime.activity_signal = 0.62
        runtime.agent_activity_level = 0.58
        runtime.agent_count_active = 3
        runtime.coordination_density = 0.52
        runtime.routing_activity = 0.57
        runtime.interaction_activity = 0.44
        runtime.memory_activity = 0.39
        runtime.heavy_inference_suppressed = True
        runtime.semantic_activity_source_summary = "agent:0.58, routing:0.57, interaction:0.44"
        runtime.lease_owner = "dali-fishtank:test"

        state = runtime._runtime_state_fields()
        for key in (
            "activity_signal",
            "agent_activity_level",
            "agent_count_active",
            "coordination_density",
            "routing_activity",
            "interaction_activity",
            "memory_activity",
            "heavy_inference_suppressed",
            "semantic_activity_source_summary",
        ):
            self.assertIn(key, state)
        self.assertEqual(state["agent_count_active"], 3)
        self.assertTrue(state["heavy_inference_suppressed"])


if __name__ == "__main__":
    unittest.main()
