import unittest
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer, MirrorState


class TestCathedralMotifActivation(unittest.TestCase):
    def _renderer_stub(self) -> FishTankRenderer:
        renderer = FishTankRenderer.__new__(FishTankRenderer)
        renderer.motif_weights = {"cathedral": 0.92}
        renderer.mirror_state = MirrorState()
        renderer.motif_activation = {}
        renderer.cadence_phase = {
            "micro_pulse": 0.4,
            "cognition_cycle": 0.5,
            "reflection_sweep": 0.6,
            "dream_cadence": 0.7,
        }
        return renderer

    def test_identity_core_is_persistent(self):
        renderer = self._renderer_stub()
        mirror = MirrorState(reasoning=0.72, attention=0.64, learning=0.58, coherence=0.66, overload=0.22, reflection_phase=0.43)
        motif = renderer._derive_motif_activation(mirror)
        self.assertEqual(motif["identity_core"], 1.0)
        self.assertGreater(motif["eye"], 0.6)
        self.assertGreater(motif["halo"], 0.6)

    def test_motif_uniform_vectors_include_collapse_mix(self):
        renderer = self._renderer_stub()
        renderer.mirror_state = MirrorState(collapse_risk=0.74, overload=0.62, repair_progress=0.18)
        renderer.motif_activation = {
            "identity_core": 1.0,
            "eye": 0.7,
            "clockwork": 0.6,
            "halo": 0.8,
            "murmuration": 0.65,
            "slime_trails": 0.52,
            "memory_constellations": 0.44,
        }
        row_a, row_b = renderer._motif_uniform_vectors()
        self.assertEqual(len(row_a), 4)
        self.assertEqual(len(row_b), 4)
        self.assertGreater(row_b[3], 0.6)
        self.assertLessEqual(max(row_a + row_b), 1.0)
        self.assertGreaterEqual(min(row_a + row_b), 0.0)

    def test_cadence_uniform_vector_contract(self):
        renderer = self._renderer_stub()
        vec = renderer._cadence_uniform_vector()
        self.assertEqual(len(vec), 4)
        for value in vec:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_activity_signal_keeps_motifs_alive(self):
        renderer = self._renderer_stub()
        renderer.activity_signal = 0.66
        renderer.agent_activity_level = 0.62
        renderer.coordination_density = 0.68
        renderer.routing_activity = 0.72
        renderer.memory_activity = 0.58
        mirror = MirrorState(
            baseline=0.6,
            reasoning=0.34,
            insight=0.2,
            learning=0.4,
            attention=0.38,
            overload=0.22,
            coherence=0.46,
            reflection_phase=0.55,
        )
        motif = renderer._derive_motif_activation(mirror)
        self.assertGreaterEqual(motif["eye"], 0.55)
        self.assertGreaterEqual(motif["halo"], 0.55)
        self.assertGreaterEqual(motif["murmuration"], 0.55)
        self.assertGreaterEqual(motif["slime_trails"], 0.56)

    def test_eye_anchor_remains_dominant_over_atmospheric_motifs(self):
        renderer = self._renderer_stub()
        renderer.activity_signal = 0.22
        renderer.agent_activity_level = 0.24
        renderer.coordination_density = 0.28
        renderer.routing_activity = 0.26
        renderer.memory_activity = 0.34
        mirror = MirrorState(
            baseline=0.58,
            reasoning=0.51,
            insight=0.34,
            learning=0.42,
            attention=0.44,
            overload=0.18,
            coherence=0.62,
            reflection_phase=0.47,
        )
        motif = renderer._derive_motif_activation(mirror)
        self.assertGreaterEqual(motif["eye"], motif["murmuration"])
        self.assertGreaterEqual(motif["eye"], motif["memory_constellations"])
        self.assertGreaterEqual(motif["clockwork"], 0.42)

    def test_novel_layers_track_clockwork_growth_and_memory(self):
        renderer = self._renderer_stub()
        renderer.activity_signal = 0.68
        renderer.routing_activity = 0.64
        renderer.interaction_activity = 0.58
        renderer.motif_activation = {
            "clockwork": 0.82,
            "slime_trails": 0.76,
            "memory_constellations": 0.72,
        }
        renderer.ecosystem_state = {
            "ecosystem_activity": 0.74,
            "colony_stability": 0.66,
            "growth_front_intensity": 0.71,
            "synchronization_pulse": 0.62,
            "ecological_memory": 0.69,
            "colony_competition": 0.28,
        }
        mirror = MirrorState(reasoning=0.61, learning=0.67, insight=0.44, attention=0.52, coherence=0.57)
        novel = renderer._derive_novel_layer_activation(mirror)
        self.assertEqual(set(novel.keys()), {
            "automaton_caravans",
            "mycelial_veins",
            "sigil_blooms",
            "chrysalis_nests",
            "spore_bursts",
        })
        self.assertGreater(novel["automaton_caravans"], 0.6)
        self.assertGreater(novel["mycelial_veins"], 0.6)
        self.assertGreater(novel["chrysalis_nests"], 0.6)


if __name__ == "__main__":
    unittest.main()
