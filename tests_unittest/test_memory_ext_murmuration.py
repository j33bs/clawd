import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.murmuration_protocol import BoundedContext, apply_local_rule, emergent_state, murmurate


class TestMemoryExtMurmuration(unittest.TestCase):
    def test_fixed_state_yields_fixed_action(self):
        state = {"stress": 0.8, "energy": 0.2, "harmony": 0.1, "silence": 0.0}
        self.assertEqual(apply_local_rule(state)["action"], "moderate")
        out = murmurate(state)
        self.assertEqual(out["local_action"], "moderate")


# ---------------------------------------------------------------------------
# apply_local_rule — threshold classification
# ---------------------------------------------------------------------------

class TestApplyLocalRule(unittest.TestCase):
    """Tests for apply_local_rule() — stress/harmony/energy/silence branches."""

    def test_high_stress_gives_moderate(self):
        self.assertEqual(apply_local_rule({"stress": 0.7})["action"], "moderate")

    def test_high_harmony_gives_align(self):
        # stress < 0.7, harmony >= 0.7
        self.assertEqual(apply_local_rule({"stress": 0.0, "harmony": 0.9})["action"], "align")

    def test_high_energy_gives_amplify(self):
        self.assertEqual(
            apply_local_rule({"stress": 0.0, "harmony": 0.0, "energy": 0.9})["action"], "amplify"
        )

    def test_high_silence_gives_reach_out(self):
        self.assertEqual(
            apply_local_rule({"stress": 0.0, "harmony": 0.0, "energy": 0.0, "silence": 0.9})["action"],
            "reach_out",
        )

    def test_no_dominant_gives_stabilize(self):
        self.assertEqual(apply_local_rule({})["action"], "stabilize")

    def test_returns_stress_energy_harmony_keys(self):
        result = apply_local_rule({"stress": 0.5, "energy": 0.5, "harmony": 0.5})
        for key in ("action", "stress", "energy", "harmony"):
            self.assertIn(key, result)

    def test_stress_priority_over_harmony(self):
        # stress=0.8 > harmony=0.9 — stress branch fires first
        self.assertEqual(apply_local_rule({"stress": 0.8, "harmony": 0.9})["action"], "moderate")

    def test_missing_keys_default_to_zero(self):
        # Empty dict → all default to 0.0 → stabilize
        self.assertEqual(apply_local_rule({})["action"], "stabilize")


# ---------------------------------------------------------------------------
# BoundedContext
# ---------------------------------------------------------------------------

class TestBoundedContext(unittest.TestCase):
    """Tests for BoundedContext — circular neighbor buffer."""

    def test_observe_adds_neighbor(self):
        ctx = BoundedContext()
        ctx.observe({"stress": 0.5})
        self.assertEqual(len(ctx.neighbors), 1)

    def test_observe_caps_at_max_neighbors(self):
        ctx = BoundedContext(max_neighbors=3)
        for i in range(10):
            ctx.observe({"stress": float(i) / 10})
        self.assertEqual(len(ctx.neighbors), 3)

    def test_observe_keeps_last_entries(self):
        ctx = BoundedContext(max_neighbors=2)
        ctx.observe({"x": 1})
        ctx.observe({"x": 2})
        ctx.observe({"x": 3})
        xs = [n["x"] for n in ctx.neighbors]
        self.assertEqual(xs, [2, 3])

    def test_empty_context_no_neighbors(self):
        ctx = BoundedContext()
        self.assertEqual(ctx.neighbors, [])

    def test_observe_copies_dict(self):
        ctx = BoundedContext()
        d = {"a": 1}
        ctx.observe(d)
        d["a"] = 99
        self.assertEqual(ctx.neighbors[0]["a"], 1)


# ---------------------------------------------------------------------------
# emergent_state
# ---------------------------------------------------------------------------

class TestEmergentState(unittest.TestCase):
    """Tests for emergent_state() — coherence/direction aggregation."""

    def test_empty_contexts_returns_stable(self):
        result = emergent_state([])
        self.assertEqual(result["direction"], "stable")
        self.assertAlmostEqual(result["coherence"], 0.0)

    def test_single_dominant_action(self):
        ctx = BoundedContext()
        for _ in range(3):
            ctx.observe({"stress": 0.9})
        result = emergent_state([ctx])
        self.assertEqual(result["direction"], "moderate")
        self.assertAlmostEqual(result["coherence"], 1.0)

    def test_coherence_in_unit_interval(self):
        ctx = BoundedContext()
        ctx.observe({"stress": 0.9})
        ctx.observe({"harmony": 0.9, "stress": 0.0})
        result = emergent_state([ctx])
        self.assertGreaterEqual(result["coherence"], 0.0)
        self.assertLessEqual(result["coherence"], 1.0)

    def test_energy_averaged(self):
        ctx = BoundedContext()
        ctx.observe({"energy": 0.8, "harmony": 0.0, "stress": 0.0})
        ctx.observe({"energy": 0.8, "harmony": 0.0, "stress": 0.0})
        result = emergent_state([ctx])
        # apply_local_rule for energy=0.8 → "amplify"; energy is passed through
        self.assertAlmostEqual(result["energy"], 0.8)

    def test_has_required_keys(self):
        result = emergent_state([])
        for key in ("coherence", "direction", "energy"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
