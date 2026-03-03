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
from hivemind.physarum_router import PhysarumRouter  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
