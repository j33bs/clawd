import tempfile
import unittest
from pathlib import Path

from core_infra.tick_microstructure import (
    append_jsonl,
    load_tick_feature_snapshot,
    prune_trade_window,
    summarize_trade_window,
    write_tick_feature_snapshot,
)


class TickMicrostructureTests(unittest.TestCase):
    def test_summarize_trade_window_computes_imbalance_and_spread(self):
        trades = [
            {"ts": 1_000, "price": 100.0, "qty": 1.0, "side": "buy"},
            {"ts": 2_000, "price": 100.5, "qty": 2.0, "side": "buy"},
            {"ts": 3_000, "price": 100.25, "qty": 1.0, "side": "sell"},
        ]
        out = summarize_trade_window("BTCUSDT", trades, best_bid=100.2, best_ask=100.3)
        self.assertEqual(out["trade_count"], 3)
        self.assertGreater(out["imbalance"], 0.0)
        self.assertGreater(out["window_return"], 0.0)
        self.assertIsNotNone(out["spread_bps"])

    def test_prune_trade_window_discards_old_ticks(self):
        trades = [
            {"ts": 1_000, "price": 100.0, "qty": 1.0, "side": "buy"},
            {"ts": 10_000, "price": 101.0, "qty": 1.0, "side": "buy"},
        ]
        prune_trade_window(trades, now_ts=20_000, lookback_ms=5_000)
        self.assertEqual(len(trades), 0)

    def test_snapshot_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tick_path = root / "ticks.jsonl"
            append_jsonl(tick_path, {"symbol": "BTCUSDT", "ts": 123, "price": 100.0})
            self.assertIn("BTCUSDT", tick_path.read_text(encoding="utf-8"))

            snapshot_path = root / "tick_features.json"
            write_tick_feature_snapshot(snapshot_path, {"BTCUSDT": {"trade_count": 5, "imbalance": 0.2, "asof_ts": 123}})
            loaded = load_tick_feature_snapshot(snapshot_path)
            self.assertEqual(loaded["BTCUSDT"]["trade_count"], 5)


if __name__ == "__main__":
    unittest.main()
