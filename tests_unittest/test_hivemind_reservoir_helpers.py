"""Tests for pure helpers in workspace/hivemind/hivemind/reservoir.py.

All stdlib — no network, no file I/O, no external deps.

Covers:
- _tanh
- _safe_float
- _feature_items
- _hash_bucket
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESERVOIR_PATH = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "reservoir.py"

_spec = _ilu.spec_from_file_location("hivemind_reservoir_real", str(RESERVOIR_PATH))
res = _ilu.module_from_spec(_spec)
sys.modules["hivemind_reservoir_real"] = res
_spec.loader.exec_module(res)


# ---------------------------------------------------------------------------
# _tanh
# ---------------------------------------------------------------------------

class TestTanh(unittest.TestCase):
    """Tests for _tanh() — wraps math.tanh."""

    def test_zero(self):
        self.assertAlmostEqual(res._tanh(0.0), 0.0)

    def test_positive(self):
        self.assertGreater(res._tanh(1.0), 0.0)
        self.assertLess(res._tanh(1.0), 1.0)

    def test_negative(self):
        self.assertLess(res._tanh(-1.0), 0.0)

    def test_large_positive_near_one(self):
        self.assertAlmostEqual(res._tanh(100.0), 1.0, places=5)

    def test_large_negative_near_minus_one(self):
        self.assertAlmostEqual(res._tanh(-100.0), -1.0, places=5)

    def test_returns_float(self):
        self.assertIsInstance(res._tanh(0.5), float)


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat(unittest.TestCase):
    """Tests for _safe_float() — coerce int/float, else 0.0."""

    def test_int_converted(self):
        self.assertAlmostEqual(res._safe_float(3), 3.0)

    def test_float_unchanged(self):
        self.assertAlmostEqual(res._safe_float(3.14), 3.14)

    def test_string_returns_zero(self):
        self.assertAlmostEqual(res._safe_float("hello"), 0.0)

    def test_none_returns_zero(self):
        self.assertAlmostEqual(res._safe_float(None), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(res._safe_float(1), float)

    def test_negative(self):
        self.assertAlmostEqual(res._safe_float(-5), -5.0)


# ---------------------------------------------------------------------------
# _feature_items
# ---------------------------------------------------------------------------

class TestFeatureItems(unittest.TestCase):
    """Tests for _feature_items() — yield (key, weight) pairs from structured data."""

    def test_string_yields_tokens(self):
        result = list(res._feature_items("hello world"))
        keys = [k for k, _ in result]
        self.assertIn(":hello", keys)
        self.assertIn(":world", keys)

    def test_string_values_lowercased(self):
        result = list(res._feature_items("Hello World"))
        keys = [k for k, _ in result]
        self.assertIn(":hello", keys)
        self.assertNotIn(":Hello", keys)

    def test_dict_yields_nested_keys(self):
        result = list(res._feature_items({"a": 1.0}))
        keys = [k for k, _ in result]
        self.assertIn("a", keys)

    def test_list_yields_indexed(self):
        result = list(res._feature_items([1, 2]))
        keys = [k for k, _ in result]
        self.assertTrue(any("[0]" in k for k in keys))
        self.assertTrue(any("[1]" in k for k in keys))

    def test_numeric_value_yielded(self):
        result = list(res._feature_items(42.0))
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][1], 42.0)

    def test_dict_sorted_keys(self):
        result = list(res._feature_items({"b": 1.0, "a": 2.0}))
        keys = [k for k, _ in result]
        # "a" should come before "b" since keys are sorted
        self.assertLess(keys.index("a"), keys.index("b"))

    def test_returns_iterable(self):
        result = list(res._feature_items("test"))
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# _hash_bucket
# ---------------------------------------------------------------------------

class TestHashBucket(unittest.TestCase):
    """Tests for _hash_bucket() — SHA-256 based bucket assignment."""

    def test_returns_int(self):
        self.assertIsInstance(res._hash_bucket("hello", 32), int)

    def test_in_range(self):
        for dim in [8, 16, 32, 64, 128]:
            result = res._hash_bucket("test", dim)
            self.assertGreaterEqual(result, 0)
            self.assertLess(result, dim)

    def test_deterministic(self):
        a = res._hash_bucket("same-text", 64)
        b = res._hash_bucket("same-text", 64)
        self.assertEqual(a, b)

    def test_different_texts_usually_differ(self):
        results = {res._hash_bucket(f"text-{i}", 64) for i in range(10)}
        self.assertGreater(len(results), 1)

    def test_empty_string(self):
        result = res._hash_bucket("", 32)
        self.assertGreaterEqual(result, 0)
        self.assertLess(result, 32)


if __name__ == "__main__":
    unittest.main()
