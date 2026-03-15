import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer, MirrorState


class TestCathedralCollapseRepair(unittest.TestCase):
    def _renderer_stub(self) -> FishTankRenderer:
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.control_bus = mock.Mock()
        renderer.control_bus.state_path = REPO_ROOT / "workspace" / "runtime" / "control_bus_state.json"
        renderer.control_bus.active_transient.return_value = {}
        renderer.palette_mode = "dali"
        renderer.exposure_base = 1.52
        renderer.bloom_strength = 0.58
        renderer.bloom_enabled = True
        renderer.contrast_base = 1.12
        renderer.saturation_base = 1.08
        renderer.temporal_alpha_base = 0.94
        renderer.particles_target = 180000
        renderer.particles_visible = 150000
        renderer.agent_count = 220000
        renderer.state_hue_mix = {"semantic_energy": 0.56}
        renderer.shader_params = {
            "luminosity": 0.56,
            "turbulence": 0.22,
            "vortex": 0.36,
            "cloud": 0.33,
            "velocity": 0.42,
        }
        renderer.mirror_state = MirrorState()
        renderer.motif_activation = {
            "identity_core": 1.0,
            "eye": 0.62,
            "clockwork": 0.58,
            "halo": 0.68,
            "murmuration": 0.52,
            "slime_trails": 0.54,
            "memory_constellations": 0.46,
        }
        renderer.cadence_modulation = {
            "glow_intensity": 0.48,
            "rotation_speed": 0.56,
            "trail_decay": 0.61,
            "swarm_clustering": 0.52,
        }
        renderer._curiosity_pulse_until = 0.0
        renderer._rd_inject_until = 0.0
        renderer._rd_inject_seed = 0.0
        renderer._last_control_file_ts = 0.0
        renderer._control_file_cache = {}
        renderer.rd_feed_base = 0.0367
        renderer.rd_kill_base = 0.0649
        renderer.rd_du_base = 0.16
        renderer.rd_dv_base = 0.08
        renderer.rd_dt_base = 1.0
        return renderer

    def test_state_transition_vector_contract(self):
        renderer = self._renderer_stub()
        renderer.mirror_state = MirrorState(collapse_risk=0.68, repair_progress=0.34, coherence=0.42, overload=0.71)
        vec = renderer._state_transition_vector()
        self.assertEqual(len(vec), 4)
        self.assertAlmostEqual(vec[0], 0.68, places=6)
        self.assertAlmostEqual(vec[1], 0.34, places=6)
        self.assertAlmostEqual(vec[2], 0.42, places=6)
        self.assertAlmostEqual(vec[3], 0.71, places=6)

    def test_collapse_visual_path_increases_turbulence_and_reduces_saturation(self):
        renderer = self._renderer_stub()
        renderer.collapse_visual_intensity = 0.78
        renderer.repair_visual_intensity = 0.16
        renderer._refresh_control_values()
        self.assertGreater(renderer.shader_params["turbulence"], 0.28)
        self.assertLess(renderer.effective_saturation, renderer.saturation_base)
        self.assertLessEqual(renderer.effective_exposure, 1.95)

    def test_repair_visual_path_reduces_motion_and_boosts_trail_persistence(self):
        renderer = self._renderer_stub()
        renderer.collapse_visual_intensity = 0.12
        renderer.repair_visual_intensity = 0.82
        renderer._refresh_control_values()
        self.assertLess(renderer.shader_params["velocity"], 0.46)
        self.assertGreater(renderer.temporal_alpha, renderer.temporal_alpha_base * 0.9)
        self.assertGreater(renderer.effective_saturation, 0.95)


if __name__ == "__main__":
    unittest.main()
