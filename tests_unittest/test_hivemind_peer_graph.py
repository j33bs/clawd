import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.peer_graph import PeerGraph, _clamp, _EdgeState  # noqa: E402


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


class TestClamp(unittest.TestCase):
    """Tests for peer_graph._clamp() — bounded clamping."""

    def test_below_low_returns_low(self):
        self.assertAlmostEqual(_clamp(-5.0, 0.0, 1.0), 0.0)

    def test_above_high_returns_high(self):
        self.assertAlmostEqual(_clamp(2.0, 0.0, 1.0), 1.0)

    def test_within_range_unchanged(self):
        self.assertAlmostEqual(_clamp(0.5, 0.0, 1.0), 0.5)

    def test_exactly_at_low(self):
        self.assertAlmostEqual(_clamp(0.0, 0.0, 1.0), 0.0)

    def test_exactly_at_high(self):
        self.assertAlmostEqual(_clamp(1.0, 0.0, 1.0), 1.0)

    def test_returns_float(self):
        self.assertIsInstance(_clamp(0.5, 0.0, 1.0), float)


class TestEdgeState(unittest.TestCase):
    """Tests for peer_graph._EdgeState — dataclass round-trip."""

    def test_to_dict_contains_weight(self):
        e = _EdgeState(weight=0.75)
        d = e.to_dict()
        self.assertAlmostEqual(d["weight"], 0.75)

    def test_to_dict_contains_all_fields(self):
        e = _EdgeState(weight=1.0, success_ema=0.5, latency_ema=100.0, tokens_ema=50.0, touches=3, last_touch_t=9.9)
        d = e.to_dict()
        for key in ("weight", "success_ema", "latency_ema", "tokens_ema", "touches", "last_touch_t"):
            self.assertIn(key, d)

    def test_from_dict_roundtrip(self):
        e = _EdgeState(weight=0.8, success_ema=0.3, latency_ema=200.0, tokens_ema=40.0, touches=5, last_touch_t=12.3)
        restored = _EdgeState.from_dict(e.to_dict())
        self.assertAlmostEqual(restored.weight, e.weight)
        self.assertAlmostEqual(restored.success_ema, e.success_ema)
        self.assertEqual(restored.touches, e.touches)

    def test_from_dict_defaults_on_missing_keys(self):
        e = _EdgeState.from_dict({"weight": 0.5})
        self.assertAlmostEqual(e.success_ema, 0.0)
        self.assertAlmostEqual(e.latency_ema, 0.0)
        self.assertEqual(e.touches, 0)

    def test_from_dict_returns_edge_state(self):
        result = _EdgeState.from_dict({"weight": 1.0})
        self.assertIsInstance(result, _EdgeState)


class TestPeerGraphPure(unittest.TestCase):
    """Tests for PeerGraph pure-ish query methods."""

    def setUp(self):
        agents = ["a", "b", "c", "d", "e"]
        self.graph = PeerGraph.init(agents, k=3, seed=42)

    def test_edge_weight_returns_float(self):
        src = "a"
        dst = self.graph.peers(src)[0]
        result = self.graph.edge_weight(src, dst)
        self.assertIsInstance(result, float)

    def test_edge_weight_nonexistent_is_zero(self):
        result = self.graph.edge_weight("a", "zzz_unknown")
        self.assertAlmostEqual(result, 0.0)

    def test_snapshot_is_dict(self):
        snap = self.graph.snapshot()
        self.assertIsInstance(snap, dict)

    def test_snapshot_has_edges(self):
        snap = self.graph.snapshot()
        self.assertIn("edges", snap)

    def test_load_roundtrip(self):
        snap = self.graph.snapshot()
        restored = PeerGraph.load(snap)
        self.assertEqual(restored.snapshot()["edges"], snap["edges"])

    def test_anneal_temperature_returns_float(self):
        result = self.graph.anneal_temperature(arousal=0.5)
        self.assertIsInstance(result, float)

    def test_anneal_temperature_bounded(self):
        # temperature should be in (0, 1] range conceptually
        result = self.graph.anneal_temperature(arousal=0.5)
        self.assertGreater(result, 0.0)

    def test_current_churn_probability_returns_float(self):
        result = self.graph.current_churn_probability(arousal=0.5)
        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()

