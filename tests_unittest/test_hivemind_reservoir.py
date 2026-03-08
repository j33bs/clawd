import math
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.reservoir import Reservoir, _tanh, _safe_float, _feature_items, _hash_bucket  # noqa: E402


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


class TestReservoir(unittest.TestCase):
    def test_deterministic_step_with_seed(self):
        r1 = Reservoir.init(dim=20, leak=0.4, spectral_scale=0.9, seed=42)
        r2 = Reservoir.init(dim=20, leak=0.4, spectral_scale=0.9, seed=42)
        s1 = r1.step({"intent": "audit"}, {"agent": "main"}, {"deg": 3})
        s2 = r2.step({"intent": "audit"}, {"agent": "main"}, {"deg": 3})
        self.assertEqual([round(x, 8) for x in s1], [round(x, 8) for x in s2])

    def test_state_decays_with_no_input(self):
        r = Reservoir.init(dim=16, leak=0.35, spectral_scale=0.8, seed=9)
        first = r.step({"x": 2.0}, {"y": 1.0}, {"z": 1.0})
        baseline = sum(abs(v) for v in first)
        for _ in range(15):
            r.step({}, {}, {})
        decayed = sum(abs(v) for v in r.step({}, {}, {}))
        self.assertLess(decayed, baseline)

    def test_similar_inputs_yield_correlated_states(self):
        r = Reservoir.init(dim=18, leak=0.3, spectral_scale=0.7, seed=5)
        s1 = r.step({"intent": "memory query"}, {"agent": "main"}, {"peers": ["a", "b"]})
        r.reset("s2")
        s2 = r.step({"intent": "memory lookup"}, {"agent": "main"}, {"peers": ["a", "b"]})
        self.assertGreater(_cos(s1, s2), 0.55)


class TestTanh(unittest.TestCase):
    """Tests for reservoir._tanh() — math.tanh wrapper."""

    def test_zero_returns_zero(self):
        self.assertAlmostEqual(_tanh(0.0), 0.0)

    def test_large_positive_approaches_one(self):
        self.assertGreater(_tanh(10.0), 0.99)

    def test_large_negative_approaches_minus_one(self):
        self.assertLess(_tanh(-10.0), -0.99)

    def test_returns_float(self):
        self.assertIsInstance(_tanh(1.0), float)

    def test_odd_function(self):
        self.assertAlmostEqual(_tanh(-0.5), -_tanh(0.5), places=10)


class TestSafeFloat(unittest.TestCase):
    """Tests for reservoir._safe_float() — numeric coercion."""

    def test_int_coerced(self):
        self.assertAlmostEqual(_safe_float(5), 5.0)

    def test_float_passthrough(self):
        self.assertAlmostEqual(_safe_float(3.14), 3.14)

    def test_string_returns_zero(self):
        self.assertAlmostEqual(_safe_float("hello"), 0.0)

    def test_none_returns_zero(self):
        self.assertAlmostEqual(_safe_float(None), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(_safe_float(1), float)


class TestFeatureItems(unittest.TestCase):
    """Tests for reservoir._feature_items() — recursive feature extractor."""

    def test_dict_yields_leaf_values(self):
        items = list(_feature_items({"a": 1.0}))
        self.assertGreater(len(items), 0)
        keys, vals = zip(*items)
        self.assertIn(1.0, vals)

    def test_string_yields_tokens(self):
        items = list(_feature_items("hello world"))
        keys = [k for k, v in items]
        self.assertTrue(any("hello" in k for k in keys))

    def test_list_yields_indexed_items(self):
        items = list(_feature_items([1.0, 2.0]))
        self.assertGreater(len(items), 0)

    def test_float_yields_single_item(self):
        items = list(_feature_items(3.14))
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(items[0][1], 3.14)

    def test_nested_dict_traversed(self):
        items = list(_feature_items({"outer": {"inner": 42.0}}))
        vals = [v for k, v in items]
        self.assertIn(42.0, vals)

    def test_prefix_propagated(self):
        items = list(_feature_items({"x": 1.0}, prefix="root"))
        keys = [k for k, v in items]
        self.assertTrue(any("root" in k for k in keys))

    def test_returns_iterable(self):
        import collections.abc
        result = _feature_items({"a": 1.0})
        self.assertIsInstance(result, collections.abc.Iterable)


class TestHashBucket(unittest.TestCase):
    """Tests for reservoir._hash_bucket() — deterministic bucket assignment."""

    def test_returns_int(self):
        self.assertIsInstance(_hash_bucket("hello", 64), int)

    def test_in_range(self):
        dim = 32
        result = _hash_bucket("hello", dim)
        self.assertGreaterEqual(result, 0)
        self.assertLess(result, dim)

    def test_deterministic(self):
        self.assertEqual(_hash_bucket("hello", 64), _hash_bucket("hello", 64))

    def test_different_texts_different_buckets(self):
        # Not guaranteed, but highly likely for these two
        b1 = _hash_bucket("alpha", 64)
        b2 = _hash_bucket("beta", 64)
        # They might collide, but let's check at least one varies
        b3 = _hash_bucket("gamma", 64)
        self.assertFalse(b1 == b2 == b3)


if __name__ == "__main__":
    unittest.main()

