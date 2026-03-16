import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralMirrorCadence(unittest.TestCase):
    def _renderer_stub(self) -> FishTankRenderer:
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer._cadence_anchor_ts = 100.0
        renderer._cadence_periods = {
            "micro_pulse_s": 2.8,
            "visual_cycle_s": 28.0,
            "cognition_cycle_s": 18.0,
            "reflection_sweep_s": 240.0,
            "dream_cycle_s": 120.0,
        }
        renderer.last_dream_ts = 0.0
        renderer.cadence_phase = {}
        renderer.cadence_modulation = {}
        return renderer

    def test_cadence_values_stay_in_bounds(self):
        renderer = self._renderer_stub()
        phase = renderer._update_cadence(now=130.0)
        for key in ("micro_pulse", "cognition_cycle", "reflection_sweep", "dream_cadence", "telluric_resonance", "visual_pulse"):
            self.assertGreaterEqual(phase[key], 0.0)
            self.assertLessEqual(phase[key], 1.0)
        for key in ("micro_pulse_phase", "visual_cycle_phase", "cognition_cycle_phase", "reflection_sweep_phase", "dream_cycle_phase"):
            self.assertGreaterEqual(phase[key], 0.0)
            self.assertLessEqual(phase[key], 1.0)
        for key in ("glow_intensity", "halo_breathing", "rotation_speed", "trail_decay", "swarm_clustering", "branching_pressure", "substrate_drift"):
            value = renderer.cadence_modulation[key]
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_cadence_evolves_over_time(self):
        renderer = self._renderer_stub()
        first = renderer._update_cadence(now=145.0)
        second = renderer._update_cadence(now=146.2)
        self.assertNotEqual(first["micro_pulse_phase"], second["micro_pulse_phase"])
        self.assertNotEqual(first["visual_cycle_phase"], second["visual_cycle_phase"])
        self.assertNotEqual(first["cognition_cycle_phase"], second["cognition_cycle_phase"])
        self.assertNotEqual(first["reflection_sweep_phase"], second["reflection_sweep_phase"])

    def test_dream_cadence_tied_to_last_dream_activity(self):
        renderer = self._renderer_stub()
        renderer.last_dream_ts = 200.0
        near = renderer._update_cadence(now=201.0)["dream_cadence"]
        far = renderer._update_cadence(now=260.0)["dream_cadence"]
        self.assertGreater(near, far)


if __name__ == "__main__":
    unittest.main()
