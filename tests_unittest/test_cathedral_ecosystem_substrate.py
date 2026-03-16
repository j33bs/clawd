import unittest
from pathlib import Path
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralEcosystemSubstrate(unittest.TestCase):
    def _renderer(self) -> FishTankRenderer:
        with mock.patch.object(FishTankRenderer, "_init_gpu_backend"):
            return FishTankRenderer(headless=True, require_gpu=False)

    def test_ecosystem_state_export_is_present_and_bounded(self):
        renderer = self._renderer()
        telemetry = {
            "gpu_temp": 49.0,
            "gpu_util": 0.62,
            "gpu_vram": 0.48,
            "gpu_vram_used_mb": 3400.0,
            "cpu_temp": 58.0,
            "fan_gpu": 1280.0,
            "disk_io": 0.25,
        }
        tacti = {
            "arousal": 0.58,
            "memory_recall_density": 0.44,
            "token_flux": 0.52,
            "research_depth": 0.63,
            "goal_conflict": 0.22,
            "active_agents": ["a", "b", "c"],
        }
        renderer.update_signals(telemetry, tacti)
        state = renderer.capture_state()
        self.assertIn("ecosystem_state", state)
        self.assertIn("ecosystem_activity", state)
        self.assertIn("growth_front_intensity", state)
        self.assertIn("decay_field_intensity", state)
        self.assertIn("substrate_excitation", state)
        self.assertIn("void_ratio", state)
        self.assertIn("seed_region_count", state)
        self.assertIn("active_colony_area", state)
        self.assertIn("dreamscape_density", state)
        self.assertIn("landscape_maturity", state)
        self.assertIn("landscape_session_seconds", state)
        self.assertIn("colony_count_estimate", state)
        self.assertIn("dormant_region_ratio", state)
        self.assertIn("thriving_region_ratio", state)
        self.assertIn("contested_region_ratio", state)
        self.assertIn("territory_entropy", state)
        self.assertIn("microbe_density", state)
        self.assertIn("division_rate", state)
        self.assertIn("substrate_health", state)
        self.assertIn("morphogenesis_level", state)
        self.assertIn("membrane_density", state)
        self.assertIn("filament_activity", state)
        self.assertIn("necrosis_front_intensity", state)
        self.assertIn("habitat_complexity", state)
        self.assertIn("nursery_count", state)
        self.assertIn("district_entropy", state)
        self.assertIn("route_ecology_strength", state)
        self.assertIn("ocular_emergence", state)
        self.assertIn("rib_emergence", state)
        self.assertIn("wing_emergence", state)
        self.assertIn("spine_emergence", state)
        self.assertIn("gear_ossification", state)
        self.assertIn("angelic_presence", state)
        self.assertIn("daemonic_pressure", state)
        self.assertIn("serpentine_force", state)
        self.assertIn("trickster_play", state)
        self.assertIn("ritual_coherence", state)
        self.assertIn("archetype_emergence_level", state)
        self.assertIn("cathedral_scene_weight", state)
        self.assertIn("ossuary_scene_weight", state)
        self.assertIn("labyrinth_scene_weight", state)
        self.assertIn("carnival_scene_weight", state)
        self.assertIn("hybrid_plaza_weight", state)
        self.assertIn("scene_attractors", state)
        self.assertIn("cathedral", state["scene_attractors"])
        self.assertIn("hybrid", state["scene_attractors"])
        self.assertGreaterEqual(int(state["colony_count_estimate"]), 0)
        self.assertGreaterEqual(int(state["seed_region_count"]), 0)
        self.assertGreaterEqual(int(state["nursery_count"]), 0)
        for key in (
            "ecosystem_activity",
            "colony_stability",
            "growth_front_intensity",
            "decay_field_intensity",
            "synchronization_pulse",
            "automata_phase",
            "substrate_excitation",
            "void_ratio",
            "active_colony_area",
            "dreamscape_density",
            "landscape_maturity",
            "landscape_session_seconds",
            "dormant_region_ratio",
            "thriving_region_ratio",
            "contested_region_ratio",
            "territory_entropy",
            "microbe_density",
            "division_rate",
            "substrate_health",
            "morphogenesis_level",
            "membrane_density",
            "filament_activity",
            "necrosis_front_intensity",
            "habitat_complexity",
            "district_entropy",
            "route_ecology_strength",
            "ocular_emergence",
            "rib_emergence",
            "wing_emergence",
            "spine_emergence",
            "gear_ossification",
            "angelic_presence",
            "daemonic_pressure",
            "serpentine_force",
            "trickster_play",
            "ritual_coherence",
            "archetype_emergence_level",
            "cathedral_scene_weight",
            "ossuary_scene_weight",
            "labyrinth_scene_weight",
            "carnival_scene_weight",
            "hybrid_plaza_weight",
        ):
            value = float(state[key])
            self.assertGreaterEqual(value, 0.0, key)
            self.assertLessEqual(value, 1.0, key)
        for attractor in state["scene_attractors"].values():
            self.assertGreaterEqual(float(attractor["x"]), -1.0)
            self.assertLessEqual(float(attractor["x"]), 1.0)
            self.assertGreaterEqual(float(attractor["y"]), -1.0)
            self.assertLessEqual(float(attractor["y"]), 1.0)
            self.assertGreaterEqual(float(attractor["radius"]), 0.0)
            self.assertLessEqual(float(attractor["radius"]), 1.0)
            self.assertGreaterEqual(float(attractor["strength"]), 0.0)
            self.assertLessEqual(float(attractor["strength"]), 1.0)

    def test_ecosystem_memory_has_temporal_persistence_but_remains_bounded(self):
        renderer = self._renderer()
        high_tacti = {
            "arousal": 0.74,
            "memory_recall_density": 0.38,
            "token_flux": 0.78,
            "research_depth": 0.72,
            "goal_conflict": 0.34,
            "active_agents": ["a", "b", "c", "d", "e"],
        }
        low_tacti = {
            "arousal": 0.18,
            "memory_recall_density": 0.72,
            "token_flux": 0.08,
            "research_depth": 0.12,
            "goal_conflict": 0.05,
            "active_agents": [],
        }
        telemetry = {"gpu_temp": 44.0, "gpu_util": 0.12, "gpu_vram": 0.2, "gpu_vram_used_mb": 1200.0, "cpu_temp": 45.0}
        renderer.update_signals(telemetry, high_tacti)
        peak = float(renderer.capture_state()["ecosystem_state"].get("ecological_memory", 0.0))
        for _ in range(4):
            renderer.update_signals(telemetry, low_tacti)
        after = float(renderer.capture_state()["ecosystem_state"].get("ecological_memory", 0.0))
        self.assertGreater(peak, 0.02)
        self.assertGreater(after, 0.01)
        self.assertLessEqual(after, 1.0)
        self.assertLessEqual(float(renderer.capture_state()["ecosystem_activity"]), 1.0)

    def test_persistent_memory_biases_seeds_without_starting_half_built(self):
        renderer = self._renderer()
        renderer._dreamscape_session_seconds = 0.0
        renderer.colony_memory_state = {
            "colony_memory_level": 0.92,
            "route_reinforcement": 0.88,
            "dormant_zone_ratio": 0.18,
            "scar_tissue_intensity": 0.26,
            "repair_zone_intensity": 0.44,
            "stabilized_habitat_ratio": 0.81,
            "ecological_persistence": 0.94,
            "memory_flux": 0.28,
        }
        telemetry = {
            "gpu_temp": 44.0,
            "gpu_util": 0.18,
            "gpu_vram": 0.24,
            "gpu_vram_used_mb": 1400.0,
            "cpu_temp": 46.0,
        }
        tacti = {
            "arousal": 0.24,
            "memory_recall_density": 0.52,
            "token_flux": 0.10,
            "research_depth": 0.14,
            "goal_conflict": 0.08,
            "active_agents": [],
        }
        renderer.update_signals(telemetry, tacti)
        state = renderer.capture_state()
        self.assertLess(float(state["landscape_maturity"]), 0.35)
        self.assertGreaterEqual(float(state["void_ratio"]), 0.35)
        self.assertLess(float(state["dreamscape_density"]), 0.20)

    def test_early_session_surfaces_seed_territory_before_habitats(self):
        renderer = self._renderer()
        renderer.display_mode_active = True
        renderer._dreamscape_session_anchor_mono = renderer.last_frame_ts - 120.0
        renderer._dreamscape_session_seconds = 0.0
        renderer.colony_memory_state = {
            "colony_memory_level": 0.44,
            "route_reinforcement": 0.38,
            "dormant_zone_ratio": 0.16,
            "scar_tissue_intensity": 0.08,
            "repair_zone_intensity": 0.18,
            "stabilized_habitat_ratio": 0.22,
            "ecological_persistence": 0.36,
            "memory_flux": 0.12,
        }
        telemetry = {
            "gpu_temp": 45.0,
            "gpu_util": 0.16,
            "gpu_vram": 0.22,
            "gpu_vram_used_mb": 1300.0,
            "cpu_temp": 47.0,
        }
        tacti = {
            "arousal": 0.28,
            "memory_recall_density": 0.48,
            "token_flux": 0.16,
            "research_depth": 0.20,
            "goal_conflict": 0.10,
            "active_agents": ["a"],
        }
        for _ in range(24):
            renderer.update_signals(telemetry, tacti)
        state = renderer.capture_state()
        self.assertGreaterEqual(int(state["seed_region_count"]), 2)
        self.assertGreater(float(state["active_colony_area"]), 0.04)
        self.assertLess(float(state["habitat_complexity"]), 0.45)
        self.assertLess(float(state["dreamscape_density"]), 0.20)

    def test_ecosystem_uniform_vectors_contract(self):
        renderer = self._renderer()
        renderer.ecosystem_state = {
            "ecosystem_activity": 0.72,
            "colony_stability": 0.65,
            "growth_front_intensity": 0.58,
            "decay_field_intensity": 0.24,
            "synchronization_pulse": 0.51,
            "substrate_excitation": 0.63,
            "colony_count_estimate": 12,
            "automata_phase": 0.33,
            "colony_competition": 0.48,
            "colony_recovery": 0.56,
            "ecological_memory": 0.61,
            "dormant_region_ratio": 0.29,
            "microbe_density": 0.48,
            "division_rate": 0.41,
            "substrate_health": 0.67,
            "morphogenesis_level": 0.53,
            "membrane_density": 0.46,
            "filament_activity": 0.62,
            "necrosis_front_intensity": 0.2,
            "habitat_complexity": 0.58,
            "nursery_count": 9,
            "district_entropy": 0.38,
            "route_ecology_strength": 0.55,
        }
        row_a, row_b, row_c = renderer._ecosystem_uniform_vectors()
        self.assertEqual(len(row_a), 4)
        self.assertEqual(len(row_b), 4)
        self.assertEqual(len(row_c), 4)
        row_d = renderer._ecosystem_stage_uniform_vector()
        self.assertEqual(len(row_d), 4)
        for value in row_d:
            self.assertGreaterEqual(float(value), 0.0)
            self.assertLessEqual(float(value), 1.0)
        for value in row_a + row_b + row_c:
            self.assertGreaterEqual(float(value), 0.0)
            self.assertLessEqual(float(value), 1.0)

    def test_scene_attractor_uniform_vectors_contract(self):
        renderer = self._renderer()
        renderer.scene_attractors = {
            "cathedral": {"x": -0.42, "y": -0.18, "radius": 0.34, "strength": 0.62},
            "ossuary": {"x": 0.48, "y": 0.24, "radius": 0.28, "strength": 0.51},
            "labyrinth": {"x": 0.32, "y": -0.56, "radius": 0.40, "strength": 0.46},
            "carnival": {"x": -0.54, "y": 0.44, "radius": 0.30, "strength": 0.38},
            "hybrid": {"x": 0.02, "y": 0.04, "radius": 0.36, "strength": 0.58},
        }
        rows = renderer._scene_attractor_uniform_vectors()
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(len(row), 4)
            self.assertGreaterEqual(float(row[0]), -1.0)
            self.assertLessEqual(float(row[0]), 1.0)
            self.assertGreaterEqual(float(row[1]), -1.0)
            self.assertLessEqual(float(row[1]), 1.0)
            self.assertGreaterEqual(float(row[2]), 0.0)
            self.assertLessEqual(float(row[2]), 1.0)
            self.assertGreaterEqual(float(row[3]), 0.0)
            self.assertLessEqual(float(row[3]), 1.0)


if __name__ == "__main__":
    unittest.main()
