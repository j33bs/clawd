"""Tests for pure helpers in workspace/memory_ext/murmuration_protocol.py.

All functions are pure (stdlib only, no I/O).

Covers:
- BoundedContext.observe() — appends and trims neighbors list
- apply_local_rule(perceived_state) — threshold-based action routing
- emergent_state(contexts) — coherence/direction/energy aggregation
- murmurate(conversation_state) — combined entry point
"""
import unittest

from workspace.memory_ext.murmuration_protocol import (
    BoundedContext,
    apply_local_rule,
    emergent_state,
    murmurate,
)


# ---------------------------------------------------------------------------
# BoundedContext
# ---------------------------------------------------------------------------


class TestBoundedContext(unittest.TestCase):
    """Tests for BoundedContext — sliding window of neighbor observations."""

    def test_default_max_neighbors(self):
        ctx = BoundedContext()
        self.assertEqual(ctx.max_neighbors, 7)

    def test_observe_appends(self):
        ctx = BoundedContext()
        ctx.observe({"stress": 0.5})
        self.assertEqual(len(ctx.neighbors), 1)

    def test_observe_stores_copy(self):
        ctx = BoundedContext()
        state = {"stress": 0.3}
        ctx.observe(state)
        state["stress"] = 0.9  # mutate original
        self.assertEqual(ctx.neighbors[0]["stress"], 0.3)

    def test_observe_trims_to_max_neighbors(self):
        ctx = BoundedContext(max_neighbors=3)
        for i in range(6):
            ctx.observe({"index": i})
        self.assertEqual(len(ctx.neighbors), 3)

    def test_observe_keeps_last_n(self):
        ctx = BoundedContext(max_neighbors=2)
        ctx.observe({"index": 0})
        ctx.observe({"index": 1})
        ctx.observe({"index": 2})
        self.assertEqual(ctx.neighbors[0]["index"], 1)
        self.assertEqual(ctx.neighbors[1]["index"], 2)

    def test_observe_none_stores_empty_dict(self):
        ctx = BoundedContext()
        ctx.observe(None)
        self.assertEqual(ctx.neighbors[0], {})

    def test_custom_max_neighbors(self):
        ctx = BoundedContext(max_neighbors=2)
        self.assertEqual(ctx.max_neighbors, 2)

    def test_neighbors_starts_empty(self):
        ctx = BoundedContext()
        self.assertEqual(ctx.neighbors, [])


# ---------------------------------------------------------------------------
# apply_local_rule
# ---------------------------------------------------------------------------


class TestApplyLocalRule(unittest.TestCase):
    """Tests for apply_local_rule() — routes action based on metric thresholds."""

    def test_high_stress_gives_moderate(self):
        result = apply_local_rule({"stress": 0.7, "energy": 0.0, "harmony": 0.0})
        self.assertEqual(result["action"], "moderate")

    def test_stress_at_threshold_gives_moderate(self):
        result = apply_local_rule({"stress": 0.7})
        self.assertEqual(result["action"], "moderate")

    def test_high_harmony_no_stress_gives_align(self):
        result = apply_local_rule({"stress": 0.0, "harmony": 0.8, "energy": 0.0})
        self.assertEqual(result["action"], "align")

    def test_high_energy_no_stress_no_harmony_gives_amplify(self):
        result = apply_local_rule({"stress": 0.0, "harmony": 0.0, "energy": 0.9})
        self.assertEqual(result["action"], "amplify")

    def test_high_silence_gives_reach_out(self):
        result = apply_local_rule({"stress": 0.0, "harmony": 0.0, "energy": 0.0, "silence": 0.8})
        self.assertEqual(result["action"], "reach_out")

    def test_all_low_gives_stabilize(self):
        result = apply_local_rule({"stress": 0.1, "harmony": 0.1, "energy": 0.1, "silence": 0.1})
        self.assertEqual(result["action"], "stabilize")

    def test_empty_state_gives_stabilize(self):
        result = apply_local_rule({})
        self.assertEqual(result["action"], "stabilize")

    def test_stress_priority_over_harmony(self):
        # Both high — stress wins (checked first)
        result = apply_local_rule({"stress": 0.8, "harmony": 0.9})
        self.assertEqual(result["action"], "moderate")

    def test_result_includes_stress(self):
        result = apply_local_rule({"stress": 0.5})
        self.assertIn("stress", result)
        self.assertAlmostEqual(result["stress"], 0.5)

    def test_result_includes_energy(self):
        result = apply_local_rule({"energy": 0.3})
        self.assertIn("energy", result)
        self.assertAlmostEqual(result["energy"], 0.3)

    def test_result_includes_harmony(self):
        result = apply_local_rule({"harmony": 0.6})
        self.assertIn("harmony", result)
        self.assertAlmostEqual(result["harmony"], 0.6)

    def test_below_threshold_not_moderate(self):
        result = apply_local_rule({"stress": 0.69})
        self.assertNotEqual(result["action"], "moderate")


# ---------------------------------------------------------------------------
# emergent_state
# ---------------------------------------------------------------------------


class TestEmergentState(unittest.TestCase):
    """Tests for emergent_state(contexts) — coherence and direction from contexts."""

    def _ctx_with(self, states):
        ctx = BoundedContext()
        for s in states:
            ctx.observe(s)
        return ctx

    def test_empty_contexts_returns_stable(self):
        result = emergent_state([])
        self.assertEqual(result["direction"], "stable")
        self.assertAlmostEqual(result["coherence"], 0.0)

    def test_single_context_single_neighbor(self):
        ctx = self._ctx_with([{"stress": 0.9}])
        result = emergent_state([ctx])
        self.assertEqual(result["direction"], "moderate")
        self.assertAlmostEqual(result["coherence"], 1.0)

    def test_uniform_actions_give_full_coherence(self):
        ctx = self._ctx_with([
            {"stress": 0.8},
            {"stress": 0.9},
            {"stress": 0.75},
        ])
        result = emergent_state([ctx])
        self.assertAlmostEqual(result["coherence"], 1.0)
        self.assertEqual(result["direction"], "moderate")

    def test_mixed_actions_reduce_coherence(self):
        ctx = self._ctx_with([
            {"stress": 0.9},  # moderate
            {"harmony": 0.9, "stress": 0.0},  # align
        ])
        result = emergent_state([ctx])
        self.assertLess(result["coherence"], 1.0)

    def test_returns_coherence_key(self):
        ctx = self._ctx_with([{"stress": 0.5}])
        result = emergent_state([ctx])
        self.assertIn("coherence", result)

    def test_returns_direction_key(self):
        ctx = self._ctx_with([{"energy": 0.8}])
        result = emergent_state([ctx])
        self.assertIn("direction", result)

    def test_returns_energy_key(self):
        ctx = self._ctx_with([{"energy": 0.8}])
        result = emergent_state([ctx])
        self.assertIn("energy", result)

    def test_energy_averaged_across_neighbors(self):
        ctx = self._ctx_with([
            {"energy": 0.8},
            {"energy": 0.4},
        ])
        result = emergent_state([ctx])
        # Both give amplify (energy >= 0.7 for first, not second → second is stabilize)
        # avg_energy = (0.8 + 0.4) / 2 = 0.6
        self.assertAlmostEqual(result["energy"], 0.6, places=5)

    def test_empty_context_neighbors_skipped(self):
        ctx = BoundedContext()  # no observations
        result = emergent_state([ctx])
        self.assertEqual(result["direction"], "stable")


# ---------------------------------------------------------------------------
# murmurate
# ---------------------------------------------------------------------------


class TestMurmurate(unittest.TestCase):
    """Tests for murmurate() — single-call entry point combining all logic."""

    def test_returns_dict(self):
        result = murmurate({"stress": 0.5})
        self.assertIsInstance(result, dict)

    def test_has_coherence(self):
        result = murmurate({"harmony": 0.8})
        self.assertIn("coherence", result)

    def test_has_direction(self):
        result = murmurate({"stress": 0.9})
        self.assertIn("direction", result)

    def test_has_energy(self):
        result = murmurate({"energy": 0.5})
        self.assertIn("energy", result)

    def test_has_local_action(self):
        result = murmurate({"stress": 0.5})
        self.assertIn("local_action", result)

    def test_high_stress_local_action_moderate(self):
        result = murmurate({"stress": 0.9})
        self.assertEqual(result["local_action"], "moderate")

    def test_stabilize_state(self):
        result = murmurate({"stress": 0.0, "harmony": 0.0, "energy": 0.0})
        self.assertEqual(result["local_action"], "stabilize")

    def test_empty_state(self):
        result = murmurate({})
        self.assertEqual(result["local_action"], "stabilize")

    def test_coherence_is_one_for_single_observation(self):
        # Single observation → only one action → 100% coherence
        result = murmurate({"stress": 0.8})
        self.assertAlmostEqual(result["coherence"], 1.0)


if __name__ == "__main__":
    unittest.main()
