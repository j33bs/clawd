import math
import unittest
from core_infra.regime_detector import detect_regime, _clean_prices


class TestRegimeDetector(unittest.TestCase):
    def test_insufficient_data(self):
        out = detect_regime([100.0, 100.1])
        self.assertEqual(out["regime"], "sideways")
        self.assertEqual(out["confidence"], 0.0)

    def test_uptrend_bull(self):
        prices = [100.0 + i for i in range(200)]
        out = detect_regime(prices, {"lookback": 100})
        self.assertEqual(out["regime"], "bull")
        self.assertGreater(out["confidence"], 0.0)

    def test_downtrend_bear(self):
        prices = [200.0 - i for i in range(200)]
        out = detect_regime(prices, {"lookback": 100})
        self.assertEqual(out["regime"], "bear")
        self.assertGreater(out["confidence"], 0.0)

    def test_flat_sideways(self):
        prices = [100.0 for _ in range(200)]
        out = detect_regime(prices, {"lookback": 100})
        self.assertEqual(out["regime"], "sideways")


class TestCleanPrices(unittest.TestCase):
    """Tests for regime_detector._clean_prices() — price sanitizer."""

    def test_valid_prices_preserved(self):
        result = _clean_prices([100.0, 101.0, 102.0])
        self.assertEqual(result, [100.0, 101.0, 102.0])

    def test_zero_prices_removed(self):
        result = _clean_prices([0.0, 100.0, 0.0, 101.0])
        self.assertEqual(result, [100.0, 101.0])

    def test_negative_prices_removed(self):
        result = _clean_prices([-10.0, 100.0])
        self.assertEqual(result, [100.0])

    def test_nan_prices_removed(self):
        result = _clean_prices([float("nan"), 100.0])
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0], 100.0)

    def test_non_numeric_removed(self):
        result = _clean_prices(["bad", 100.0])
        self.assertEqual(result, [100.0])

    def test_empty_returns_empty(self):
        self.assertEqual(_clean_prices([]), [])

    def test_returns_list(self):
        self.assertIsInstance(_clean_prices([1.0]), list)


class TestDetectRegimeExtended(unittest.TestCase):
    """Additional tests for detect_regime edge cases."""

    def test_features_key_present(self):
        out = detect_regime([100.0 + i for i in range(20)])
        self.assertIn("features", out)

    def test_confidence_in_unit_interval(self):
        prices = [100.0 + i * 2.0 for i in range(100)]
        out = detect_regime(prices)
        self.assertGreaterEqual(out["confidence"], 0.0)
        self.assertLessEqual(out["confidence"], 1.0)

    def test_regime_is_string(self):
        out = detect_regime([100.0, 101.0, 102.0, 103.0])
        self.assertIsInstance(out["regime"], str)

    def test_regime_valid_value(self):
        out = detect_regime([100.0, 101.0, 102.0, 103.0])
        self.assertIn(out["regime"], {"bull", "bear", "sideways"})

    def test_mixed_invalid_prices_handled(self):
        # Only 2 valid prices → insufficient data path
        out = detect_regime([0.0, float("nan"), "bad", 100.0, 100.1])
        self.assertIn("regime", out)


if __name__ == "__main__":
    unittest.main()
