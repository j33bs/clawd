import unittest

from core_infra.fill_simulator import estimate_liquidation_price, limit_fill_price, market_fill_price


class FillSimulatorTests(unittest.TestCase):
    def test_market_fill_uses_quote_side_and_costs(self):
        out = market_fill_price(
            side="buy",
            reference_price=100.0,
            best_bid=99.9,
            best_ask=100.1,
            slippage_bps=2.0,
            impact_bps_per_10k=1.0,
            notional_usd=5000.0,
        )
        self.assertGreater(out["price"], 100.1)
        self.assertEqual(out["role"], "taker")

    def test_limit_fill_requires_touch(self):
        self.assertIsNone(limit_fill_price(side="buy", limit_price=100.0, trade_price=100.5))
        out = limit_fill_price(side="buy", limit_price=100.0, trade_price=99.9)
        self.assertIsNotNone(out)
        self.assertEqual(out["price"], 100.0)
        self.assertEqual(out["role"], "maker")

    def test_estimate_liquidation_price_supports_long_and_short(self):
        long_liq = estimate_liquidation_price(100.0, 1, 5.0, 0.01)
        short_liq = estimate_liquidation_price(100.0, -1, 5.0, 0.01)
        self.assertLess(long_liq, 100.0)
        self.assertGreater(short_liq, 100.0)


if __name__ == "__main__":
    unittest.main()
