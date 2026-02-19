import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.peer_graph import PeerGraph  # noqa: E402


class TestPeerGraph(unittest.TestCase):
    def test_seeded_init_is_deterministic(self):
        agents = ["a1", "a2", "a3", "a4", "a5", "a6"]
        g1 = PeerGraph.init(agents, k=3, seed=7)
        g2 = PeerGraph.init(agents, k=3, seed=7)
        self.assertEqual(g1.snapshot()["edges"], g2.snapshot()["edges"])

    def test_peer_count_invariant_is_maintained(self):
        agents = ["n1", "n2", "n3", "n4", "n5", "n6", "n7"]
        graph = PeerGraph.init(agents, k=4, seed=11)
        for _ in range(30):
            graph.tick(1.0)
            for src in agents:
                peers = graph.peers(src)
                self.assertEqual(len(peers), 4)
                self.assertNotIn(src, peers)
                self.assertEqual(len(set(peers)), len(peers))

    def test_positive_signal_increases_edge_weight(self):
        agents = ["u1", "u2", "u3", "u4", "u5", "u6"]
        graph = PeerGraph.init(agents, k=3, seed=1)
        src = "u1"
        dst = graph.peers(src)[0]
        before = graph.edge_weight(src, dst)
        for _ in range(12):
            graph.observe_interaction(
                src,
                dst,
                {"success": True, "latency": 20, "tokens": 40, "user_reward": 1.0},
            )
            graph.tick(0.5)
        after = graph.edge_weight(src, dst)
        self.assertGreater(after, before)
        self.assertIn(dst, graph.peers(src))


if __name__ == "__main__":
    unittest.main()

