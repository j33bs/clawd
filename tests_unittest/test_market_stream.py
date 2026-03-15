import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import market_stream  # noqa: E402


class MarketStreamTests(unittest.TestCase):
    def test_classify_symbol_provider_distinguishes_venue_shapes(self):
        self.assertEqual(market_stream.classify_symbol_provider("BTCUSDT"), "legacy_crypto")
        self.assertEqual(market_stream.classify_symbol_provider("BTC/USD"), "kraken_spot")
        self.assertEqual(market_stream.classify_symbol_provider("AAPL"), "alpaca_equity")

    def test_normalize_binance_klines(self):
        rows = market_stream._normalize_binance_klines(
            "BTCUSDT",
            "15m",
            [
                [1000, "1.0", "2.0", "0.5", "1.5", "42.0"],
            ],
        )
        self.assertEqual(
            rows,
            [
                {
                    "symbol": "BTCUSDT",
                    "ts": 1000,
                    "o": 1.0,
                    "h": 2.0,
                    "l": 0.5,
                    "c": 1.5,
                    "v": 42.0,
                    "interval": "15m",
                    "source": "binance",
                }
            ],
        )

    def test_merge_rows_replaces_duplicate_symbol_timestamp(self):
        existing = [{"symbol": "BTCUSDT", "ts": 1000, "c": 1.0}]
        incoming = [{"symbol": "BTCUSDT", "ts": 1000, "c": 2.0}, {"symbol": "ETHUSDT", "ts": 1000, "c": 3.0}]
        out = market_stream.merge_rows(existing, incoming)
        self.assertEqual(out, [{"symbol": "BTCUSDT", "ts": 1000, "c": 2.0}, {"symbol": "ETHUSDT", "ts": 1000, "c": 3.0}])

    def test_fetch_public_klines_falls_back_to_bybit(self):
        calls = []

        def fake_request(url):
            calls.append(url)
            if "binance" in url:
                raise RuntimeError("binance blocked")
            return {
                "result": {
                    "list": [
                        ["1000", "1.0", "2.0", "0.5", "1.5", "42.0"],
                    ]
                }
            }

        out = market_stream.fetch_public_klines("BTCUSDT", "15m", 10, request_json=fake_request)
        self.assertEqual(out[0]["source"], "bybit")
        self.assertEqual(len(calls), 2)

    def test_fetch_public_klines_uses_kraken_for_spot_pairs(self):
        calls = []

        def fake_request(url, timeout=30, headers=None):
            calls.append((url, headers))
            return {
                "error": [],
                "result": {
                    "BTC/USD": [
                        [1000, "1.0", "2.0", "0.5", "1.5", "1.4", "42.0", 7],
                    ],
                    "last": 1001,
                },
            }

        out = market_stream.fetch_public_klines("BTC/USD", "15m", 10, request_json=fake_request)
        self.assertEqual(out[0]["symbol"], "BTC/USD")
        self.assertEqual(out[0]["source"], "kraken")
        self.assertEqual(len(calls), 1)

    def test_fetch_public_klines_uses_yahoo_fallback_for_equities(self):
        def fake_request(url, timeout=30, headers=None):
            self.assertIn("query1.finance.yahoo.com", url)
            return {
                "chart": {
                    "result": [
                        {
                            "timestamp": [1700000000],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": [100.0],
                                        "high": [101.0],
                                        "low": [99.5],
                                        "close": [100.5],
                                        "volume": [12345],
                                    }
                                ]
                            },
                        }
                    ],
                    "error": None,
                }
            }

        with mock.patch.dict(os.environ, {"OPENCLAW_PUBLIC_EQUITY_PROVIDER": "yahoo"}, clear=False):
            out = market_stream.fetch_public_klines("AAPL", "15m", 10, request_json=fake_request)
        self.assertEqual(out[0]["symbol"], "AAPL")
        self.assertEqual(out[0]["source"], "yahoo")

    def test_fetch_public_klines_requires_alpaca_credentials_when_public_fallback_disabled(self):
        with mock.patch.dict(os.environ, {"OPENCLAW_PUBLIC_EQUITY_PROVIDER": "off"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "alpaca_credentials_missing"):
                market_stream.fetch_public_klines("AAPL", "15m", 10, request_json=lambda *args, **kwargs: {})

    def test_run_writes_expected_candle_files(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            config_path = tmp / "system1_trading.yaml"
            config_path.write_text(
                "sims:\n"
                "  - id: SIM_A\n"
                "    strategy: regime_gated_long_flat\n"
                "    universe:\n"
                "      - BTCUSDT\n"
                "      - ETHUSDT\n",
                encoding="utf-8",
            )

            def fake_fetcher(symbol, interval, limit):
                base = 1000 if symbol == "BTCUSDT" else 2000
                step = 100 if interval == "15m" else 200
                return [
                    {
                        "symbol": symbol,
                        "ts": base,
                        "o": 1.0,
                        "h": 2.0,
                        "l": 0.5,
                        "c": 1.5,
                        "v": 42.0,
                        "interval": interval,
                        "source": "test",
                    },
                    {
                        "symbol": symbol,
                        "ts": base + step,
                        "o": 1.1,
                        "h": 2.1,
                        "l": 0.6,
                        "c": 1.6,
                        "v": 43.0,
                        "interval": interval,
                        "source": "test",
                    },
                ]

            market_dir = tmp / "market"
            market_stream.run(
                config_path=config_path,
                limit=2,
                full=True,
                market_dir=market_dir,
                fetcher=fake_fetcher,
            )

            candles_15m = market_stream.load_jsonl(market_dir / "candles_15m.jsonl")
            candles_1h = market_stream.load_jsonl(market_dir / "candles_1h.jsonl")
            self.assertEqual(len(candles_15m), 4)
            self.assertEqual(len(candles_1h), 4)
            self.assertEqual({row["symbol"] for row in candles_15m}, {"BTCUSDT", "ETHUSDT"})


if __name__ == "__main__":
    unittest.main()
