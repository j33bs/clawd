import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sim_runner


class SimRunnerTickModeTests(unittest.TestCase):
    def test_run_supports_tick_and_quote_strategies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            market_dir = root / "market"
            market_dir.mkdir(parents=True, exist_ok=True)

            config_path = root / "system1_trading.yaml"
            config_path.write_text(
                "sims:\n"
                "  - id: SIM_D\n"
                "    strategy: tick_crypto_scalping\n"
                "    mode: tick\n"
                "    universe:\n"
                "      - BTCUSDT\n"
                "    capital: 1000\n"
                "    dd_kill: 0.2\n"
                "    daily_loss: 0.1\n"
                "    max_trades_per_day: 40\n"
                "  - id: SIM_F\n"
                "    strategy: cross_exchange_spread_arbitrage\n"
                "    mode: quote\n"
                "    universe:\n"
                "      - BTCUSDT\n"
                "    capital: 1000\n"
                "    dd_kill: 0.2\n"
                "    daily_loss: 0.1\n"
                "    max_trades_per_day: 40\n",
                encoding="utf-8",
            )
            features_path = root / "system1_trading.features.yaml"
            features_path.write_text("features:\n  competing_models: true\n", encoding="utf-8")

            (market_dir / "candles_15m.jsonl").write_text(
                "".join(
                    '{"symbol":"BTCUSDT","ts":%d,"o":100.0,"h":100.5,"l":99.8,"c":%.4f,"v":1.0}\n'
                    % (idx * 900000, 100.0 + (idx * 0.2))
                    for idx in range(6)
                ),
                encoding="utf-8",
            )
            (market_dir / "candles_1h.jsonl").write_text(
                "".join(
                    '{"symbol":"BTCUSDT","ts":%d,"o":100.0,"h":100.6,"l":99.7,"c":%.4f,"v":1.0}\n'
                    % (idx * 3600000, 100.0 + (idx * 0.5))
                    for idx in range(3)
                ),
                encoding="utf-8",
            )

            tick_lines = []
            quote_lines = []
            for idx in range(35):
                ts = idx * 10000
                price = 100.0 + (idx * 0.03)
                tick_lines.append(
                    json.dumps(
                        {
                            "type": "aggTrade",
                            "symbol": "BTCUSDT",
                            "ts": ts,
                            "price": price,
                            "qty": 0.5,
                            "side": "buy",
                            "trade_id": idx,
                        }
                    )
                )
                quote_lines.append(
                    json.dumps(
                        {
                            "symbol": "BTCUSDT",
                            "venue": "binance_spot",
                            "ts": ts,
                            "best_bid": price - 0.01,
                            "best_ask": price + 0.01,
                            "mid_price": price,
                            "spread_bps": 2.0,
                        }
                    )
                )
            quote_lines.extend(
                [
                    json.dumps(
                        {
                            "symbol": "BTCUSDT",
                            "venue": "bybit_spot",
                            "ts": 150000,
                            "best_bid": 100.30,
                            "best_ask": 100.32,
                            "mid_price": 100.31,
                            "spread_bps": 2.0,
                        }
                    ),
                    json.dumps(
                        {
                            "symbol": "BTCUSDT",
                            "venue": "binance_spot",
                            "ts": 150000,
                            "best_bid": 100.24,
                            "best_ask": 100.26,
                            "mid_price": 100.25,
                            "spread_bps": 2.0,
                        }
                    ),
                    json.dumps(
                        {
                            "symbol": "BTCUSDT",
                            "venue": "bybit_spot",
                            "ts": 220000,
                            "best_bid": 100.255,
                            "best_ask": 100.265,
                            "mid_price": 100.26,
                            "spread_bps": 1.0,
                        }
                    ),
                ]
            )
            (market_dir / "ticks.jsonl").write_text("\n".join(tick_lines) + "\n", encoding="utf-8")
            (market_dir / "venue_quotes.jsonl").write_text("\n".join(quote_lines) + "\n", encoding="utf-8")
            (market_dir / "funding_rates.jsonl").write_text("", encoding="utf-8")
            (market_dir / "tick_features.json").write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            (market_dir / "cross_exchange_features.json").write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            (market_dir / "funding_snapshot.json").write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")

            with patch.object(sim_runner, "BASE_DIR", root):
                with patch.object(sim_runner, "REPO_ROOT", root):
                    with patch.object(sim_runner, "CANDLES_15M", market_dir / "candles_15m.jsonl"):
                        with patch.object(sim_runner, "CANDLES_1H", market_dir / "candles_1h.jsonl"):
                            with patch.object(sim_runner, "TICKS_FILE", market_dir / "ticks.jsonl"):
                                with patch.object(sim_runner, "VENUE_QUOTES_FILE", market_dir / "venue_quotes.jsonl"):
                                    with patch.object(sim_runner, "FUNDING_HISTORY_FILE", market_dir / "funding_rates.jsonl"):
                                        with patch.object(sim_runner, "TICK_FEATURES", market_dir / "tick_features.json"):
                                            with patch.object(sim_runner, "CROSS_EXCHANGE_FILE", market_dir / "cross_exchange_features.json"):
                                                with patch.object(sim_runner, "FUNDING_SNAPSHOT_FILE", market_dir / "funding_snapshot.json"):
                                                    with patch.object(sim_runner, "get_itc_signal", return_value={"reason": "missing"}):
                                                        sim_runner.run(full=True, config_path=config_path, features_path=features_path)

            sim_d_trades = (root / "sim" / "SIM_D" / "trades.jsonl").read_text(encoding="utf-8")
            sim_f_trades = (root / "sim" / "SIM_F" / "trades.jsonl").read_text(encoding="utf-8")
            self.assertIn('"open_long"', sim_d_trades)
            self.assertIn('"open_pair"', sim_f_trades)
            self.assertTrue((root / "sim" / "SIM_D" / "state.json").exists())
            self.assertTrue((root / "sim" / "SIM_F" / "state.json").exists())

    def test_short_execution_tracks_directional_pnl(self):
        cfg = {
            "id": "SIM_SHORT",
            "strategy": "perp_funding_carry",
            "universe": ["BTCUSDT"],
            "capital": 1000.0,
            "dd_kill": 0.5,
            "daily_loss": 0.5,
            "max_trades_per_day": 20,
            "execution": {
                "max_notional_pct": 0.1,
                "taker_fee_rate": 0.0,
                "maker_fee_rate": 0.0,
                "slippage_bps": 0.0,
                "spread_bps": 0.0,
                "market_impact_bps_per_10k": 0.0,
                "funding_bps_8h": 0.0,
                "borrow_bps_daily": 0.0,
                "short_borrow_bps_daily": 0.0,
            },
        }
        with tempfile.TemporaryDirectory() as td:
            with patch.object(sim_runner, "BASE_DIR", Path(td)):
                sim = sim_runner.Sim(cfg)
                open_trade = sim._execute("BTCUSDT", "open_short", 100.0, 0, "short_open", quote={"best_bid": 100.0, "best_ask": 100.1})
                close_trade = sim._execute("BTCUSDT", "close_short", 95.0, 60000, "short_close", quote={"best_bid": 95.0, "best_ask": 95.1})
        self.assertIsNotNone(open_trade)
        self.assertIsNotNone(close_trade)
        self.assertGreater(close_trade["pnl"], 0.0)

    def test_quote_arb_honors_drawdown_halt(self):
        cfg = {
            "id": "SIM_F",
            "strategy": "cross_exchange_spread_arbitrage",
            "mode": "quote",
            "universe": ["BTCUSDT"],
            "capital": 1000.0,
            "dd_kill": 0.08,
            "daily_loss": 0.05,
            "max_trades_per_day": 20,
            "execution": {
                "max_notional_pct": 0.03,
                "leverage": 1.0,
                "taker_fee_rate": 0.001,
            },
        }
        with tempfile.TemporaryDirectory() as td:
            with patch.object(sim_runner, "BASE_DIR", Path(td)):
                sim = sim_runner.Sim(cfg)
                sim.equity = 669.30
                sim.peak_equity = 1000.0
                sim.synthetic_pairs["BTCUSDT"] = {
                    "entry_gap_bps": 5.0,
                    "notional": 20.079,
                    "open_ts": 0,
                    "cost_open": 0.040158,
                }
                trades = sim.run_quote_arb(
                    "BTCUSDT",
                    {
                        "ts": 1000,
                        "symbol": "BTCUSDT",
                        "binance_mid": 70000.0,
                        "bybit_mid": 70035.0,
                        "mid_gap_bps": 5.0,
                    },
                )
        self.assertTrue(sim.halted)
        self.assertFalse(sim.synthetic_pairs)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["reason"], "halt_exit")

    def test_funding_carry_uses_configured_entry_and_exit_thresholds(self):
        cfg = {
            "id": "SIM_G",
            "strategy": "perp_funding_carry",
            "mode": "tick",
            "universe": ["BTCUSDT"],
            "capital": 1000.0,
            "dd_kill": 0.2,
            "daily_loss": 0.1,
            "max_trades_per_day": 20,
            "execution": {
                "max_notional_pct": 0.05,
                "taker_fee_rate": 0.0,
                "maker_fee_rate": 0.0,
                "slippage_bps": 0.0,
                "spread_bps": 0.0,
                "market_impact_bps_per_10k": 0.0,
                "funding_bps_8h": 0.0,
                "borrow_bps_daily": 0.0,
                "short_borrow_bps_daily": 0.0,
                "tick_min_interval_ms": 0,
                "entry_min_abs_funding_rate": 0.000025,
                "exit_min_abs_funding_rate": 0.000012,
            },
        }
        tick_snapshot = {
            "trade_count": 120,
            "vwap": 100.0,
            "realized_vol": 0.0004,
            "spread_bps": 0.8,
            "best_bid": 99.99,
            "best_ask": 100.01,
        }
        with tempfile.TemporaryDirectory() as td:
            with patch.object(sim_runner, "BASE_DIR", Path(td)):
                sim = sim_runner.Sim(cfg)
                open_trades = sim.run_tick_funding_carry(
                    "BTCUSDT",
                    {"ts": 60_000, "price": 100.0},
                    tick_snapshot=tick_snapshot,
                    funding_row={"last_funding_rate": 0.00003},
                )
                close_trades = sim.run_tick_funding_carry(
                    "BTCUSDT",
                    {"ts": 120_000, "price": 99.8},
                    tick_snapshot=tick_snapshot,
                    funding_row={"last_funding_rate": 0.00001},
                )

        self.assertEqual(len(open_trades), 1)
        self.assertEqual(open_trades[0]["reason"], "funding_carry_short")
        self.assertEqual(len(close_trades), 1)
        self.assertEqual(close_trades[0]["reason"], "funding_carry_exit")


if __name__ == "__main__":
    unittest.main()
