import math
import unittest

from core_infra.volatility_metrics import compute_atr, compute_rolling_vol, compute_volatility


class TestVolatilityMetrics(unittest.TestCase):
    def test_atr_insufficient(self):
        out = compute_atr([], period=3)
        self.assertIsNone(out["atr"])
        self.assertEqual(out["n"], 0)

    def test_atr_basic(self):
        candles = []
        for i in range(5):
            candles.append({"h": 10 + i, "l": 9 + i, "c": 9.5 + i})
        out = compute_atr(candles, period=3)
        self.assertAlmostEqual(out["atr"], 1.5, places=6)
        self.assertIsNotNone(out["atr_pct"])

    def test_rolling_vol(self):
        prices = [100, 101, 102, 103, 104, 105]
        out = compute_rolling_vol(prices, window=3)

        rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        w = rets[-3:]
        mean = sum(w) / len(w)
        var = sum((r - mean) ** 2 for r in w) / len(w)
        expected = math.sqrt(var)

        self.assertAlmostEqual(out["rolling_vol"], expected, places=12)
        self.assertAlmostEqual(out["rolling_vol_pct"], expected * 100.0, places=12)

    def test_compute_volatility_prices_only(self):
        prices = [100, 101, 102, 103, 104, 105]
        out = compute_volatility(prices=prices, params={"vol_window": 3})
        self.assertIsNone(out["atr"])
        self.assertIsNotNone(out["rolling_vol"])


if __name__ == "__main__":
    unittest.main()
