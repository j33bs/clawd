import os
import unittest

from workspace.hivemind.hivemind.peer_graph import PeerGraph


class TestPeerGraphAnneal(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def _count_swaps(self, graph: PeerGraph, steps: int) -> int:
        swaps = 0
        previous = {agent: tuple(graph.peers(agent)) for agent in graph.snapshot()["agents"]}
        for _ in range(steps):
            graph.tick(1.0)
            current = {agent: tuple(graph.peers(agent)) for agent in graph.snapshot()["agents"]}
            for agent in previous:
                if previous[agent] != current[agent]:
                    swaps += 1
            previous = current
        return swaps

    def test_early_steps_swap_more_than_late_steps_when_enabled(self):
        os.environ["OPENCLAW_PEERGRAPH_ANNEAL"] = "1"
        graph = PeerGraph.init(["a", "b", "c", "d", "e", "f", "g"], k=3, seed=7)
        early = self._count_swaps(graph, 15)
        late = self._count_swaps(graph, 15)
        self.assertGreater(early, late)

    def test_flag_off_uses_constant_churn_probability(self):
        os.environ["OPENCLAW_PEERGRAPH_ANNEAL"] = "0"
        graph = PeerGraph.init(["a", "b", "c", "d", "e", "f"], k=2, seed=3)
        start = graph.current_churn_probability()
        graph.tick(30.0)
        end = graph.current_churn_probability()
        self.assertAlmostEqual(start, end, places=9)


if __name__ == "__main__":
    unittest.main()
