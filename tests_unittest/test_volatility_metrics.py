import math
import unittest

from core_infra.volatility_metrics import compute_volatility


class TestVolatilityMetrics(unittest.TestCase):
    def test_insufficient_data(self):
        out = compute_volatility([], {"atr_period": 3, "vol_period": 3})
        self.assertIsNone(out["atr"])
        self.assertIsNone(out["rolling_vol"])
        self.assertEqual(out["n"], 0)

    def test_atr_computation(self):
        candles = []
        for i in range(5):
            candles.append({"h": 10 + i, "l": 9 + i, "c": 9.5 + i})
        out = compute_volatility(candles, {"atr_period": 3, "vol_period": 3})
        self.assertAlmostEqual(out["atr"], 1.5, places=6)
        self.assertIsNotNone(out["atr_pct"])

    def test_rolling_vol(self):
        closes = [100, 101, 102, 103, 104, 105]
        candles = [{"c": c, "h": c + 0.5, "l": c - 0.5} for c in closes]
        out = compute_volatility(candles, {"atr_period": 2, "vol_period": 3})

        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        expected = math.sqrt(sum((r - sum(rets[-3:]) / 3) ** 2 for r in rets[-3:]) / 3)
        self.assertAlmostEqual(out["rolling_vol"], expected, places=12)
        self.assertAlmostEqual(out["rolling_vol_pct"], expected * 100.0, places=12)


if __name__ == "__main__":
    unittest.main()
