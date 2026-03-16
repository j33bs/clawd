import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import market_stream_live  # noqa: E402


class MarketStreamLiveTests(unittest.TestCase):
    def test_split_symbols_by_provider_tracks_equities_and_kraken(self):
        groups = market_stream_live._split_symbols_by_provider(["BTCUSDT", "BTC/USD", "AAPL"])
        self.assertEqual(groups["legacy_crypto"], ["BTCUSDT"])
        self.assertEqual(groups["kraken_spot"], ["BTC/USD"])
        self.assertEqual(groups["alpaca_equity"], ["AAPL"])

    def test_extract_kraken_trade_and_ticker_rows(self):
        ticker = market_stream_live._extract_kraken_ticker_row(
            {
                "channel": "ticker",
                "type": "snapshot",
                "data": [
                    {
                        "symbol": "BTC/USD",
                        "bid": 71303.7,
                        "ask": 71303.8,
                        "timestamp": "2026-03-15T02:44:19.178900Z",
                    }
                ],
            }
        )
        trades = market_stream_live._extract_kraken_trade_rows(
            {
                "channel": "trade",
                "type": "update",
                "data": [
                    {
                        "symbol": "BTC/USD",
                        "side": "buy",
                        "price": 71313.7,
                        "qty": 0.001,
                        "trade_id": 97173065,
                        "timestamp": "2026-03-15T02:44:33.484535Z",
                    }
                ],
            }
        )
        self.assertEqual(ticker["symbol"], "BTC/USD")
        self.assertEqual(ticker["best_bid"], 71303.7)
        self.assertEqual(trades[0]["symbol"], "BTC/USD")
        self.assertEqual(trades[0]["trade_id"], 97173065)

    def test_extract_kraken_ohlc_rows(self):
        rows = market_stream_live._extract_kraken_ohlc_rows(
            {
                "channel": "ohlc",
                "type": "snapshot",
                "data": [
                    {
                        "symbol": "BTC/USD",
                        "open": 71098.8,
                        "high": 71216.7,
                        "low": 71021.3,
                        "close": 71110.7,
                        "volume": 5.51009713,
                        "interval_begin": "2026-03-15T00:15:00.000000000Z",
                        "interval": 15,
                    }
                ],
            }
        )
        self.assertEqual(rows[0]["symbol"], "BTC/USD")
        self.assertEqual(rows[0]["interval"], "15m")
        self.assertEqual(rows[0]["source"], "kraken_ws")

    def test_build_stream_url_contains_expected_streams(self):
        url = market_stream_live._build_stream_url(["BTCUSDT", "ETHUSDT"])
        self.assertIn("btcusdt@kline_15m", url)
        self.assertIn("btcusdt@kline_1h", url)
        self.assertIn("ethusdt@kline_15m", url)
        self.assertIn("ethusdt@kline_1h", url)

    def test_extract_kline_row_normalizes_combined_stream_payload(self):
        row = market_stream_live._extract_kline_row(
            {
                "stream": "btcusdt@kline_15m",
                "data": {
                    "e": "kline",
                    "s": "BTCUSDT",
                    "k": {
                        "t": 1234,
                        "i": "15m",
                        "o": "1.0",
                        "h": "2.0",
                        "l": "0.5",
                        "c": "1.5",
                        "v": "42.0",
                        "x": True,
                    },
                },
            }
        )
        self.assertEqual(
            row,
            {
                "symbol": "BTCUSDT",
                "ts": 1234,
                "o": 1.0,
                "h": 2.0,
                "l": 0.5,
                "c": 1.5,
                "v": 42.0,
                "interval": "15m",
                "source": "binance_ws",
                "closed": True,
            },
        )

    def test_extract_trade_and_book_rows(self):
        trade = market_stream_live._extract_trade_row(
            {
                "data": {
                    "e": "aggTrade",
                    "s": "BTCUSDT",
                    "T": 2222,
                    "p": "101.5",
                    "q": "0.75",
                    "m": False,
                    "a": 7,
                }
            }
        )
        book = market_stream_live._extract_book_row(
            {
                "data": {
                    "e": "bookTicker",
                    "s": "BTCUSDT",
                    "E": 3333,
                    "b": "101.4",
                    "a": "101.6",
                }
            }
        )
        self.assertEqual(trade["side"], "buy")
        self.assertEqual(trade["trade_id"], 7)
        self.assertEqual(book["best_bid"], 101.4)
        self.assertEqual(book["best_ask"], 101.6)

    def test_extract_bybit_orderbook_row(self):
        row = market_stream_live._extract_bybit_orderbook_row(
            {
                "topic": "orderbook.1.BTCUSDT",
                "ts": 4444,
                "data": {
                    "b": [["101.2", "0.5"]],
                    "a": [["101.3", "0.6"]],
                },
            }
        )
        self.assertEqual(row["symbol"], "BTCUSDT")
        self.assertEqual(row["best_bid"], 101.2)
        self.assertEqual(row["best_ask"], 101.3)

    def test_update_venue_state_writes_cross_exchange_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            market_dir = Path(td)
            venue_state = {}
            market_stream_live._update_venue_quote_state(
                venue_state,
                venue="binance_spot",
                row={"symbol": "BTCUSDT", "ts": 1000, "best_bid": 100.0, "best_ask": 100.2},
                market_dir=market_dir,
            )
            market_stream_live._update_venue_quote_state(
                venue_state,
                venue="bybit_spot",
                row={"symbol": "BTCUSDT", "ts": 1005, "best_bid": 100.4, "best_ask": 100.6},
                market_dir=market_dir,
            )
            market_stream_live._write_cross_exchange_snapshot(market_dir, venue_state)
            text = (market_dir / market_stream_live.CROSS_EXCHANGE_FEATURES_FILE).read_text(encoding="utf-8")
            self.assertIn('"mid_gap_bps"', text)
            self.assertIn('"BTCUSDT"', text)

    def test_apply_row_and_flush_state_updates_existing_candle(self):
        with tempfile.TemporaryDirectory() as td:
            market_dir = Path(td)
            state = {"15m": {}}
            first = {
                "symbol": "BTCUSDT",
                "ts": 1000,
                "o": 1.0,
                "h": 2.0,
                "l": 0.5,
                "c": 1.5,
                "v": 42.0,
                "interval": "15m",
                "source": "binance_ws",
                "closed": False,
            }
            second = dict(first)
            second["c"] = 1.6

            self.assertTrue(market_stream_live._apply_row(state, first))
            self.assertTrue(market_stream_live._apply_row(state, second))
            market_stream_live._flush_state(market_dir, state)

            text = (market_dir / "candles_15m.jsonl").read_text(encoding="utf-8")
            self.assertIn('"c": 1.6', text)
            self.assertNotIn('"c": 1.5', text)


if __name__ == "__main__":
    unittest.main()
