import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = REPO_ROOT / "workspace"
if str(WORKSPACE_PATH) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_PATH))

from cathedral.fishtank_renderer import FishTankRenderer


class TestCathedralColonyMemoryWild(unittest.TestCase):
    def _renderer(self) -> FishTankRenderer:
        with mock.patch.object(FishTankRenderer, "_init_gpu_backend"):
            return FishTankRenderer(headless=True, require_gpu=False)

    def test_colony_memory_state_is_bounded_and_persistent(self):
        renderer = self._renderer()
        telemetry = {
            "gpu_temp": 52.0,
            "gpu_util": 0.66,
            "gpu_vram": 0.54,
            "gpu_vram_used_mb": 4600.0,
            "cpu_temp": 63.0,
            "fan_gpu": 1500.0,
            "disk_io": 0.22,
        }
        tacti_active = {
            "arousal": 0.74,
            "memory_recall_density": 0.48,
            "token_flux": 0.72,
            "research_depth": 0.69,
            "goal_conflict": 0.26,
            "active_agents": ["a", "b", "c", "d", "e", "f"],
        }
        tacti_quiet = {
            "arousal": 0.18,
            "memory_recall_density": 0.34,
            "token_flux": 0.04,
            "research_depth": 0.1,
            "goal_conflict": 0.03,
            "active_agents": [],
        }

        renderer.update_signals(telemetry, tacti_active)
        first = renderer.capture_state()
        first_level = float(first["colony_memory_level"])

        for _ in range(4):
            renderer.update_signals(telemetry, tacti_quiet)
        state = renderer.capture_state()

        self.assertGreater(first_level, 0.0)
        self.assertGreater(float(state["colony_memory_level"]), 0.0)
        self.assertIn("colony_memory_state", state)
        for key in (
            "colony_memory_level",
            "route_reinforcement",
            "dormant_zone_ratio",
            "scar_tissue_intensity",
            "ecological_persistence",
            "repair_zone_intensity",
            "stabilized_habitat_ratio",
        ):
            value = float(state[key])
            self.assertGreaterEqual(value, 0.0, key)
            self.assertLessEqual(value, 1.0, key)

    def test_colony_memory_remains_engaged_under_sustained_activity(self):
        telemetry = {
            "gpu_temp": 50.0,
            "gpu_util": 0.62,
            "gpu_vram": 0.48,
            "gpu_vram_used_mb": 4100.0,
            "cpu_temp": 61.0,
            "fan_gpu": 1460.0,
            "disk_io": 0.19,
        }
        tacti = {
            "arousal": 0.68,
            "memory_recall_density": 0.56,
            "token_flux": 0.58,
            "research_depth": 0.52,
            "goal_conflict": 0.12,
            "active_agents": ["a", "b", "c", "d"],
        }
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "fishtank_colony_memory_state.json"
            layers_path = Path(tmpdir) / "fishtank_colony_memory_layers.npz"
            with mock.patch("cathedral.fishtank_renderer.FISHTANK_COLONY_MEMORY_STATE_PATH", state_path), mock.patch(
                "cathedral.fishtank_renderer.FISHTANK_COLONY_MEMORY_LAYERS_PATH", layers_path
            ):
                renderer = self._renderer()
                renderer.update_signals(telemetry, tacti)
                first = float(renderer.capture_state()["colony_memory_level"])
                for _ in range(10):
                    renderer.update_signals(telemetry, tacti)
                later = float(renderer.capture_state()["colony_memory_level"])

                self.assertGreater(first, 0.04)
                self.assertGreater(later, 0.04)
                self.assertGreaterEqual(later, first - 0.02)

    def test_wild_system_exports_present_and_bounded(self):
        renderer = self._renderer()
        telemetry = {
            "gpu_temp": 47.0,
            "gpu_util": 0.51,
            "gpu_vram": 0.42,
            "gpu_vram_used_mb": 3600.0,
            "cpu_temp": 57.0,
            "fan_gpu": 1320.0,
            "disk_io": 0.18,
        }
        tacti = {
            "arousal": 0.62,
            "memory_recall_density": 0.54,
            "token_flux": 0.66,
            "research_depth": 0.71,
            "goal_conflict": 0.18,
            "active_agents": ["a", "b", "c", "d"],
        }

        renderer.update_signals(telemetry, tacti)
        state = renderer.capture_state()
        self.assertIn("wild_layer_activation", state)

        for key in (
            "chronofossil_intensity",
            "orchard_density",
            "orchard_bloom_state",
            "relay_serpent_activity",
            "moth_activity",
            "reservoir_depth",
            "reservoir_activation",
        ):
            value = float(state[key])
            self.assertGreaterEqual(value, 0.0, key)
            self.assertLessEqual(value, 1.0, key)

        moth_clusters = int(state["moth_cluster_count"])
        self.assertGreaterEqual(moth_clusters, 1)
        self.assertLessEqual(moth_clusters, 16)

    def test_wild_uniform_vectors_are_four_by_four_bounded(self):
        renderer = self._renderer()
        renderer.wild_layer_activation = {
            "chronofossil_intensity": 0.72,
            "orchard_density": 0.63,
            "orchard_bloom_state": 0.44,
            "relay_serpent_activity": 0.57,
            "moth_activity": 0.41,
            "moth_cluster_count": 9,
            "reservoir_depth": 0.76,
            "reservoir_activation": 0.29,
        }
        row_a, row_b = renderer._wild_layer_uniform_vectors()
        self.assertEqual(len(row_a), 4)
        self.assertEqual(len(row_b), 4)
        for value in row_a + row_b:
            self.assertGreaterEqual(float(value), 0.0)
            self.assertLessEqual(float(value), 1.0)

    def test_colony_memory_persists_across_renderer_restart(self):
        telemetry = {
            "gpu_temp": 49.0,
            "gpu_util": 0.58,
            "gpu_vram": 0.44,
            "gpu_vram_used_mb": 3900.0,
            "cpu_temp": 58.0,
            "fan_gpu": 1400.0,
            "disk_io": 0.16,
        }
        tacti = {
            "arousal": 0.69,
            "memory_recall_density": 0.59,
            "token_flux": 0.61,
            "research_depth": 0.63,
            "goal_conflict": 0.14,
            "active_agents": ["a", "b", "c", "d", "e"],
        }
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "fishtank_colony_memory_state.json"
            layers_path = Path(tmpdir) / "fishtank_colony_memory_layers.npz"
            with mock.patch("cathedral.fishtank_renderer.FISHTANK_COLONY_MEMORY_STATE_PATH", state_path), mock.patch(
                "cathedral.fishtank_renderer.FISHTANK_COLONY_MEMORY_LAYERS_PATH", layers_path
            ):
                renderer = self._renderer()
                for _ in range(6):
                    renderer.update_signals(telemetry, tacti)
                before = renderer.capture_state()
                self.assertGreater(float(before["colony_memory_level"]), 0.0)
                self.assertTrue(renderer._persist_colony_memory_substrate(force=True))
                self.assertTrue(state_path.exists())
                self.assertTrue(layers_path.exists())
                renderer.close()

                reloaded = self._renderer()
                after = reloaded.capture_state()
                self.assertTrue(after["colony_memory_loaded"])
                self.assertGreater(float(after["colony_memory_level"]), 0.0)
                self.assertGreater(float(after["ecological_persistence"]), 0.0)
                self.assertNotEqual(str(after["colony_memory_last_load_ts"]), "")
                self.assertAlmostEqual(
                    float(after["colony_memory_level"]),
                    float(before["colony_memory_level"]),
                    delta=0.08,
                )
                self.assertAlmostEqual(
                    float(after["route_reinforcement"]),
                    float(before["route_reinforcement"]),
                    delta=0.08,
                )


if __name__ == "__main__":
    unittest.main()
