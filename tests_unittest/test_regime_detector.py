import unittest
from core_infra.regime_detector import detect_regime


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


if __name__ == "__main__":
    unittest.main()
