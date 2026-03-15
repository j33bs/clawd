import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralMirrorState(unittest.TestCase):
    def _renderer_stub(self) -> FishTankRenderer:
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.identity_profile = "dali"
        renderer.lease_mode = "shared"
        renderer.inference_quiesced = False
        renderer._rd_inject_seed = 0.0
        renderer.shader_params = {
            "luminosity": 0.5,
            "turbulence": 0.2,
            "velocity": 0.3,
            "warmth": 0.2,
            "vortex": 0.3,
            "ripple": 0.2,
            "cloud": 0.3,
            "nebula": 0.4,
        }
        return renderer

    def test_derive_mirror_state_conflict_heavy_case(self):
        renderer = self._renderer_stub()
        telemetry = {"gpu_util": 0.88, "cpu_temp": 74.0, "cpu_util": 0.84}
        tacti = {
            "arousal": 0.92,
            "memory_recall_density": 0.08,
            "goal_conflict": 0.9,
            "research_depth": 0.72,
            "token_flux": 0.86,
        }
        state = renderer._derive_mirror_state(telemetry, tacti)
        self.assertGreater(state.overload, 0.6)
        self.assertGreater(state.collapse_risk, 0.55)
        self.assertLess(state.coherence, 0.5)

    def test_derive_mirror_state_memory_heavy_case(self):
        renderer = self._renderer_stub()
        telemetry = {"gpu_util": 0.25, "cpu_temp": 52.0, "cpu_util": 0.2}
        tacti = {
            "arousal": 0.35,
            "memory_recall_density": 0.94,
            "goal_conflict": 0.14,
            "research_depth": 0.62,
            "token_flux": 0.28,
        }
        state = renderer._derive_mirror_state(telemetry, tacti)
        self.assertGreater(state.learning, 0.6)
        self.assertGreater(state.learning, state.overload)
        self.assertGreater(state.coherence, 0.55)

    def test_derive_mirror_state_stable_case(self):
        renderer = self._renderer_stub()
        telemetry = {"gpu_util": 0.3, "cpu_temp": 49.0, "cpu_util": 0.28}
        tacti = {
            "arousal": 0.26,
            "memory_recall_density": 0.68,
            "goal_conflict": 0.06,
            "research_depth": 0.44,
            "token_flux": 0.22,
        }
        state = renderer._derive_mirror_state(telemetry, tacti)
        self.assertGreater(state.coherence, state.overload)
        self.assertGreater(state.baseline, 0.5)
        self.assertLess(state.collapse_risk, 0.4)

    def test_update_signals_marks_inferred_sources_and_hue_mix(self):
        renderer = self._renderer_stub()
        telemetry = {"gpu_util": 0.52, "gpu_vram": 0.48, "gpu_vram_used_mb": 2800.0, "cpu_temp": 60.0}
        tacti = {"arousal": 0.61, "memory_recall_density": 0.42, "token_flux": 0.55}
        renderer.update_signals(telemetry, tacti)
        self.assertIn("goal_conflict_source", renderer.mirror_state_inference)
        self.assertIn("derived", renderer.mirror_state_inference["goal_conflict_source"])
        self.assertEqual(len(renderer.state_hue_mix.get("semantic_weights_a", [])), 4)
        hue_total = sum(
            float(renderer.state_hue_mix.get(key, 0.0))
            for key in ("indigo_violet", "electric_blue", "gold", "emerald", "amber", "crimson", "white")
        )
        self.assertAlmostEqual(hue_total, 1.0, places=4)

    def test_activity_snapshot_drives_reasoning_without_faking_insight(self):
        renderer = self._renderer_stub()
        renderer.lease_mode = "exclusive"
        renderer.inference_quiesced = True
        renderer.activity_snapshot = {
            "activity_signal": 0.72,
            "agent_activity_level": 0.68,
            "agent_count_active": 5,
            "coordination_density": 0.64,
            "routing_activity": 0.71,
            "interaction_activity": 0.57,
            "memory_activity": 0.54,
            "heavy_inference_suppressed": True,
            "semantic_activity_source_summary": "agent:0.68, routing:0.71, interaction:0.57",
        }
        telemetry = {"gpu_util": 0.08, "cpu_temp": 43.0, "cpu_util": 0.18}
        tacti = {
            "arousal": 0.34,
            "memory_recall_density": 0.36,
            "goal_conflict": 0.18,
            "research_depth": 0.28,
            "token_flux": 0.14,
            "active_agents": ["a", "b", "c", "d", "e"],
        }
        state = renderer._derive_mirror_state(telemetry, tacti)
        self.assertGreater(state.reasoning, 0.42)
        self.assertGreater(state.attention, 0.35)
        self.assertLess(state.insight, 0.55)
        self.assertEqual(renderer.agent_count_active, 5)
        self.assertIn("runtime.activity_snapshot", renderer.mirror_state_inference["activity_signal_source"])


if __name__ == "__main__":
    unittest.main()
