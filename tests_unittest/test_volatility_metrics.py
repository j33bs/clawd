import math
import unittest

from core_infra.volatility_metrics import (
    compute_atr, compute_rolling_vol, compute_volatility, _get, _extract_ohlc,
)


class TestVolatilityMetrics(unittest.TestCase):
    def test_atr_insufficient(self):
        out = compute_atr([], period=3)
        self.assertIsNone(out["atr"])
        self.assertEqual(out["n"], 0)

    def test_atr_basic(self):
        candles = []
        for i in range(5):
            candles.append({"o": 9.5 + i, "h": 10 + i, "l": 9 + i, "c": 9.5 + i})
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


class TestGet(unittest.TestCase):
    """Tests for volatility_metrics._get() — aliased field lookup."""

    def test_primary_key_found(self):
        result = _get({"open": 100.0}, "open", "o")
        self.assertAlmostEqual(result, 100.0)

    def test_alias_key_used_when_primary_missing(self):
        result = _get({"o": 99.5}, "open", "o")
        self.assertAlmostEqual(result, 99.5)

    def test_none_value_falls_through(self):
        result = _get({"open": None, "o": 98.0}, "open", "o")
        self.assertAlmostEqual(result, 98.0)

    def test_no_key_returns_none(self):
        self.assertIsNone(_get({"x": 1.0}, "open", "o"))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(_get({"open": "not_a_float"}, "open"))

    def test_returns_float(self):
        result = _get({"h": 5}, "h")
        self.assertIsInstance(result, float)


class TestExtractOhlc(unittest.TestCase):
    """Tests for volatility_metrics._extract_ohlc() — candle extractor."""

    def test_valid_candle_returns_tuple(self):
        c = {"open": 9.0, "high": 10.0, "low": 8.5, "close": 9.5}
        result = _extract_ohlc(c)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 4)

    def test_alias_keys_accepted(self):
        c = {"o": 9.0, "h": 10.0, "l": 8.5, "c": 9.5}
        result = _extract_ohlc(c)
        self.assertIsNotNone(result)

    def test_missing_field_returns_none(self):
        c = {"open": 9.0, "high": 10.0, "low": 8.5}  # missing close
        self.assertIsNone(_extract_ohlc(c))

    def test_zero_high_returns_none(self):
        c = {"open": 9.0, "high": 0.0, "low": 8.5, "close": 9.0}
        self.assertIsNone(_extract_ohlc(c))

    def test_negative_close_returns_none(self):
        c = {"open": 9.0, "high": 10.0, "low": 8.5, "close": -1.0}
        self.assertIsNone(_extract_ohlc(c))

    def test_values_in_correct_order(self):
        c = {"open": 9.0, "high": 11.0, "low": 8.0, "close": 10.0}
        o, h, l, cl = _extract_ohlc(c)
        self.assertAlmostEqual(o, 9.0)
        self.assertAlmostEqual(h, 11.0)
        self.assertAlmostEqual(l, 8.0)
        self.assertAlmostEqual(cl, 10.0)


class TestComputeRollingVolEdges(unittest.TestCase):
    """Additional edge cases for compute_rolling_vol."""

    def test_too_few_prices_returns_none(self):
        out = compute_rolling_vol([100.0, 101.0], window=5)
        self.assertIsNone(out["rolling_vol"])

    def test_zero_prices_filtered_out(self):
        prices = [0.0, 0.0, 100.0, 101.0, 102.0, 103.0]
        out = compute_rolling_vol(prices, window=2)
        # zero prices stripped, so n < len(prices)
        self.assertLess(out["n"], len(prices))


class TestComputeAtrEdges(unittest.TestCase):
    """Additional edge cases for compute_atr."""

    def test_candles_with_invalid_entries_skipped(self):
        candles = [
            {"o": 9.0, "h": 10.0, "l": 8.5, "c": 9.5},  # valid
            {"o": None, "h": None, "l": None, "c": None},  # invalid
            {"o": 9.5, "h": 10.5, "l": 9.0, "c": 10.0},  # valid
        ]
        out = compute_atr(candles, period=1)
        self.assertLessEqual(out["n"], 2)

    def test_single_valid_candle_insufficient(self):
        candles = [{"o": 9.0, "h": 10.0, "l": 8.5, "c": 9.5}]
        out = compute_atr(candles, period=1)
        # need at least period+1 = 2 candles
        self.assertIsNone(out["atr"])


if __name__ == "__main__":
    unittest.main()
