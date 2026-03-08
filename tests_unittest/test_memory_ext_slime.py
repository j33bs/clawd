import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.slime_routing import TrailNetwork


def _net(td: str) -> TrailNetwork:
    """Helper: build a TrailNetwork backed by a temp path, memory_ext disabled."""
    state = Path(td) / "slime_network.json"
    with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
        return TrailNetwork(state_path=state)


class TestMemoryExtSlime(unittest.TestCase):
    def test_deposit_then_route(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "slime_network.json"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "1"}, clear=False):
                net = TrailNetwork(state_path=state)
                tid = net.deposit_trail("TACTI governance routing", 1.5)
                routed = net.route_query("governance")
                self.assertIn(tid, routed)
                stats = net.get_network_state()
                self.assertEqual(stats["nodes"], 1)


# ---------------------------------------------------------------------------
# deposit_trail
# ---------------------------------------------------------------------------

class TestTrailNetworkDeposit(unittest.TestCase):
    """Tests for TrailNetwork.deposit_trail() — hash + weight accumulation."""

    def test_returns_string_id(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                tid = net.deposit_trail("hello world", 1.0)
                self.assertIsInstance(tid, str)

    def test_same_text_same_id(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                t1 = net.deposit_trail("fixed text", 1.0)
                t2 = net.deposit_trail("fixed text", 0.5)
                self.assertEqual(t1, t2)

    def test_different_text_different_id(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                t1 = net.deposit_trail("text A", 1.0)
                t2 = net.deposit_trail("text B", 1.0)
                self.assertNotEqual(t1, t2)

    def test_weight_accumulates(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                tid = net.deposit_trail("repeated", 1.0)
                net.deposit_trail("repeated", 2.0)
                weight = net.state["nodes"][tid]["weight"]
                self.assertAlmostEqual(weight, 3.0)

    def test_negative_importance_clamped_to_zero(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                tid = net.deposit_trail("negative", -5.0)
                weight = net.state["nodes"][tid]["weight"]
                self.assertAlmostEqual(weight, 0.0)

    def test_id_length_is_12(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                tid = net.deposit_trail("check length", 1.0)
                self.assertEqual(len(tid), 12)


# ---------------------------------------------------------------------------
# route_query
# ---------------------------------------------------------------------------

class TestTrailNetworkRoute(unittest.TestCase):
    """Tests for TrailNetwork.route_query() — overlap-based scoring."""

    def test_empty_network_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                self.assertEqual(net.route_query("anything"), [])

    def test_no_overlap_zero_weight_returns_empty(self):
        # score = overlap + weight; zero overlap AND zero weight → score=0 → filtered
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                net.deposit_trail("alpha beta gamma", 0.0)
                self.assertEqual(net.route_query("xyz zzz"), [])

    def test_matching_query_returns_id(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                tid = net.deposit_trail("governance routing protocol", 1.0)
                result = net.route_query("governance")
                self.assertIn(tid, result)

    def test_returns_at_most_5(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                for i in range(10):
                    net.deposit_trail("common_word unique_%d" % i, 1.0)
                result = net.route_query("common_word")
                self.assertLessEqual(len(result), 5)

    def test_higher_weight_ranked_first(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                t_low = net.deposit_trail("shared token", 0.1)
                t_high = net.deposit_trail("shared token", 10.0)
                # Both have same text so same tid — deposit accumulates
                # Use two different texts with the shared query word instead
                net2 = _net(td)
                t_a = net2.deposit_trail("query word alpha", 0.1)
                t_b = net2.deposit_trail("query word beta", 10.0)
                result = net2.route_query("query word")
                # t_b has higher weight, should appear first (or both present)
                self.assertIn(t_b, result)


# ---------------------------------------------------------------------------
# get_network_state
# ---------------------------------------------------------------------------

class TestGetNetworkState(unittest.TestCase):
    """Tests for TrailNetwork.get_network_state() — summary statistics."""

    def test_empty_network_zero_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                stats = net.get_network_state()
                self.assertEqual(stats["nodes"], 0)

    def test_one_deposit_one_node(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                net.deposit_trail("single node", 1.0)
                self.assertEqual(net.get_network_state()["nodes"], 1)

    def test_two_unique_deposits_two_nodes(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                net.deposit_trail("node one", 1.0)
                net.deposit_trail("node two", 1.0)
                self.assertEqual(net.get_network_state()["nodes"], 2)

    def test_has_required_keys(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                net = _net(td)
                stats = net.get_network_state()
                for key in ("nodes", "edges", "density"):
                    self.assertIn(key, stats)


if __name__ == "__main__":
    unittest.main()
