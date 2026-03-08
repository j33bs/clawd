import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.peer_graph import PeerGraph  # noqa: E402
from hivemind.physarum_router import PhysarumRouter, _edge_key  # noqa: E402


class TestPhysarumRouter(unittest.TestCase):
    def test_rewarded_path_becomes_dominant(self):
        graph = PeerGraph.init(["a", "b", "c", "d", "e"], k=2, seed=3)
        router = PhysarumRouter(seed=4, explore_rate=0.0)
        paths = router.propose_paths("a", "route", graph, n_paths=3)
        self.assertTrue(paths)
        target_path = paths[0]
        for _ in range(10):
            router.update(target_path, reward_signal=1.0)
        next_paths = router.propose_paths("a", "route", graph, n_paths=1)
        self.assertEqual(next_paths[0], target_path)

    def test_prune_preserves_min_connectivity(self):
        graph = PeerGraph.init(["n1", "n2", "n3", "n4", "n5", "n6"], k=3, seed=12)
        router = PhysarumRouter(seed=21)
        for _ in range(8):
            for path in router.propose_paths("n1", "intent", graph, n_paths=4):
                router.update(path, reward_signal=0.3)
        router.prune(min_k=2, max_k=3)
        snap = router.snapshot()
        grouped = {}
        for edge in snap["conductance"].keys():
            src, dst = edge.split("->", 1)
            grouped.setdefault(src, set()).add(dst)
        for src, neighbors in grouped.items():
            self.assertGreaterEqual(len(neighbors), 2, src)

    def test_valence_weighting_adjusts_reward_when_enabled(self):
        router = PhysarumRouter(seed=5, explore_rate=0.0)
        path = ["x", "y"]
        with patch.dict(os.environ, {"OPENCLAW_TRAIL_VALENCE": "1"}, clear=False):
            router.update(path, reward_signal=1.0, valence=-1.0)
        low_cond = router.snapshot()["conductance"]["x->y"]

        router = PhysarumRouter(seed=5, explore_rate=0.0)
        with patch.dict(os.environ, {"OPENCLAW_TRAIL_VALENCE": "1"}, clear=False):
            router.update(path, reward_signal=1.0, valence=1.0)
        high_cond = router.snapshot()["conductance"]["x->y"]

        self.assertGreater(high_cond, low_cond)


class TestEdgeKey(unittest.TestCase):
    """Tests for physarum_router._edge_key() — canonical edge string."""

    def test_returns_string(self):
        self.assertIsInstance(_edge_key("a", "b"), str)

    def test_format_is_arrow(self):
        result = _edge_key("src", "dst")
        self.assertEqual(result, "src->dst")

    def test_different_order_different_key(self):
        self.assertNotEqual(_edge_key("a", "b"), _edge_key("b", "a"))

    def test_self_loop(self):
        result = _edge_key("x", "x")
        self.assertEqual(result, "x->x")


class TestPhysarumRouterPure(unittest.TestCase):
    """Tests for PhysarumRouter snapshot/load round-trip and init behavior."""

    def setUp(self):
        agents = ["a", "b", "c", "d", "e"]
        self.graph = PeerGraph.init(agents, k=2, seed=7)
        self.router = PhysarumRouter(seed=42, explore_rate=0.1)

    def test_snapshot_returns_dict(self):
        snap = self.router.snapshot()
        self.assertIsInstance(snap, dict)

    def test_snapshot_has_conductance(self):
        snap = self.router.snapshot()
        self.assertIn("conductance", snap)

    def test_snapshot_has_explore_rate(self):
        snap = self.router.snapshot()
        self.assertIn("explore_rate", snap)

    def test_load_roundtrip(self):
        # Do some updates first to have non-trivial state
        paths = self.router.propose_paths("a", "route", self.graph, n_paths=2)
        for p in paths:
            self.router.update(p, reward_signal=0.7)
        snap = self.router.snapshot()
        restored = PhysarumRouter.load(snap)
        self.assertEqual(restored.snapshot()["conductance"], snap["conductance"])

    def test_propose_paths_returns_list(self):
        result = self.router.propose_paths("a", "route", self.graph, n_paths=2)
        self.assertIsInstance(result, list)

    def test_get_conductance_default_one(self):
        # Unknown edges default to conductance 1.0 (neutral exploration bias)
        result = self.router._get_conductance("zzz_unknown", "abc_unknown")
        self.assertAlmostEqual(result, 1.0)


if __name__ == "__main__":
    unittest.main()
