import unittest

from core_infra.regime_detector import detect_regime


class TestRegimeDetector(unittest.TestCase):
    def test_insufficient_data(self):
        out = detect_regime([])
        self.assertEqual(out["regime"], "sideways")
        self.assertEqual(out["confidence"], 0.0)
        self.assertEqual(out["features"].get("reason"), "insufficient_data")

    def test_bullish_series(self):
        prices = [100.0, 102.0, 105.0, 110.0, 120.0]
        out = detect_regime(prices)
        self.assertEqual(out["regime"], "bull")
        self.assertGreaterEqual(out["confidence"], 0.9)

    def test_bearish_series(self):
        prices = [120.0, 115.0, 110.0, 105.0, 100.0]
        out = detect_regime(prices)
        self.assertEqual(out["regime"], "bear")
        self.assertGreaterEqual(out["confidence"], 0.9)

    def test_sideways_series(self):
        prices = [100.0, 100.05, 100.1, 100.08, 100.1]
        out = detect_regime(prices, {"sideways_threshold": 0.0025})
        self.assertEqual(out["regime"], "sideways")
        self.assertGreaterEqual(out["confidence"], 0.0)

    def test_ignores_invalid_prices(self):
        prices = [100.0, 0.0, -5, "bad", 101.0, float("nan"), 102.0]
        out = detect_regime(prices)
        self.assertIn(out["regime"], {"bull", "bear", "sideways"})
        self.assertIn("features", out)


if __name__ == "__main__":
    unittest.main()
