import unittest

from core_infra.strategy_blender import blend_signals, _to_float


class TestStrategyBlender(unittest.TestCase):
    def test_empty(self):
        out = blend_signals([])
        self.assertEqual(out["signal"], 0.0)
        self.assertEqual(out["confidence"], 0.0)

    def test_weighted_average(self):
        items = [
            {"source": "a", "signal": 1.0, "weight": 2.0, "confidence": 1.0},
            {"source": "b", "signal": 0.0, "weight": 1.0, "confidence": 1.0},
        ]
        out = blend_signals(items)
        self.assertAlmostEqual(out["signal"], 2.0 / 3.0, places=6)
        self.assertGreater(out["confidence"], 0.0)

    def test_tie_break(self):
        items = [
            {"source": "a", "signal": 1.0, "weight": 1.0, "confidence": 1.0},
            {"source": "b", "signal": -1.0, "weight": 1.0, "confidence": 1.0},
        ]
        out = blend_signals(items, {"tie_break": "bull"})
        self.assertEqual(out["signal"], 1.0)


class TestToFloat(unittest.TestCase):
    """Tests for strategy_blender._to_float() — safe float coercion."""

    def test_int_coerced(self):
        self.assertAlmostEqual(_to_float(42), 42.0)

    def test_string_number_coerced(self):
        self.assertAlmostEqual(_to_float("3.14"), 3.14)

    def test_non_numeric_returns_default(self):
        self.assertAlmostEqual(_to_float("not_a_number"), 0.0)

    def test_none_returns_default(self):
        self.assertAlmostEqual(_to_float(None), 0.0)

    def test_nan_returns_default(self):
        import math
        self.assertAlmostEqual(_to_float(float("nan")), 0.0)

    def test_custom_default(self):
        self.assertAlmostEqual(_to_float("bad", default=9.9), 9.9)

    def test_returns_float(self):
        self.assertIsInstance(_to_float(1), float)

    def test_negative_value(self):
        self.assertAlmostEqual(_to_float(-5.5), -5.5)


class TestBlendSignalsExtended(unittest.TestCase):
    """Additional tests for blend_signals edge cases."""

    def test_non_dict_items_skipped(self):
        items = ["string", 42, {"source": "a", "signal": 1.0, "weight": 1.0, "confidence": 1.0}]
        out = blend_signals(items)
        self.assertAlmostEqual(out["signal"], 1.0)

    def test_negative_weight_clamped_to_zero(self):
        items = [{"source": "a", "signal": 1.0, "weight": -1.0, "confidence": 1.0}]
        out = blend_signals(items)
        self.assertEqual(out["signal"], 0.0)  # no_weight path

    def test_bear_tie_break(self):
        items = [
            {"source": "a", "signal": 1.0, "weight": 1.0, "confidence": 1.0},
            {"source": "b", "signal": -1.0, "weight": 1.0, "confidence": 1.0},
        ]
        out = blend_signals(items, {"tie_break": "bear"})
        self.assertEqual(out["signal"], -1.0)

    def test_explanation_keys_present(self):
        out = blend_signals([{"source": "a", "signal": 0.5, "weight": 1.0, "confidence": 1.0}])
        self.assertIn("explanation", out)
        self.assertIn("n", out["explanation"])
        self.assertIn("method", out["explanation"])

    def test_confidence_clamped_to_unit(self):
        # confidence > 1 gets clamped
        items = [{"source": "a", "signal": 0.5, "weight": 1.0, "confidence": 5.0}]
        out = blend_signals(items)
        self.assertLessEqual(out["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
