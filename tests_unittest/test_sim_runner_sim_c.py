import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sim_runner


class SimRunnerSimCTests(unittest.TestCase):
    def test_report_strategy_alias_resolves_to_runtime_engine(self):
        cfg = {
            "id": "SIM_I",
            "strategy": "us_equity_event_impulse",
            "runtime_strategy": "itc_sentiment_tilt_long_flat",
            "universe": ["NVDA"],
            "capital": 300.0,
            "dd_kill": 0.12,
            "daily_loss": 0.04,
            "max_trades_per_day": 6,
        }

        with tempfile.TemporaryDirectory() as td:
            with patch.object(sim_runner, "BASE_DIR", Path(td)):
                sim = sim_runner.Sim(cfg)

        self.assertEqual(sim.strategy_profile, "us_equity_event_impulse")
        self.assertEqual(sim.runtime_strategy, "itc_sentiment_tilt_long_flat")
        self.assertEqual(sim.strategy, "itc_sentiment_tilt_long_flat")

    def test_sim_c_persists_model_state_and_trades(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            market_dir = root / "market"
            market_dir.mkdir(parents=True, exist_ok=True)
            config_path = root / "system1_trading.yaml"
            config_path.write_text(
                "sims:\n"
                "  - id: SIM_C\n"
                "    strategy: ensemble_competing_models_long_flat\n"
                "    universe:\n"
                "      - BTCUSDT\n"
                "    capital: 1000\n"
                "    dd_kill: 0.15\n"
                "    daily_loss: 0.05\n"
                "    max_trades_per_day: 8\n",
                encoding="utf-8",
            )
            features_path = root / "system1_trading.features.yaml"
            features_path.write_text("features:\n  competing_models: true\n", encoding="utf-8")

            candles_15m = market_dir / "candles_15m.jsonl"
            candles_1h = market_dir / "candles_1h.jsonl"
            ticks_path = market_dir / "ticks.jsonl"
            quotes_path = market_dir / "venue_quotes.jsonl"
            funding_path = market_dir / "funding_rates.jsonl"
            tick_features_path = market_dir / "tick_features.json"
            cross_exchange_path = market_dir / "cross_exchange_features.json"
            funding_snapshot_path = market_dir / "funding_snapshot.json"
            ticks_path.write_text("", encoding="utf-8")
            quotes_path.write_text("", encoding="utf-8")
            funding_path.write_text("", encoding="utf-8")
            tick_features_path.write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            cross_exchange_path.write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            funding_snapshot_path.write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            with candles_15m.open("w", encoding="utf-8") as handle:
                for idx in range(80):
                    close = 100.0 + (idx * 0.6)
                    handle.write(
                        (
                            '{"symbol":"BTCUSDT","ts":%d,"o":%.4f,"h":%.4f,"l":%.4f,"c":%.4f,"v":1.0}\n'
                            % (idx * 900000, close - 0.2, close + 0.4, close - 0.5, close)
                        )
                    )
            with candles_1h.open("w", encoding="utf-8") as handle:
                for idx in range(30):
                    close = 100.0 + (idx * 2.0)
                    handle.write(
                        (
                            '{"symbol":"BTCUSDT","ts":%d,"o":%.4f,"h":%.4f,"l":%.4f,"c":%.4f,"v":1.0}\n'
                            % (idx * 3600000, close - 0.4, close + 0.6, close - 0.7, close)
                        )
                    )

            with patch.object(sim_runner, "BASE_DIR", root):
                with patch.object(sim_runner, "REPO_ROOT", root):
                    with patch.object(sim_runner, "CANDLES_15M", candles_15m):
                        with patch.object(sim_runner, "CANDLES_1H", candles_1h):
                            with patch.object(sim_runner, "TICKS_FILE", ticks_path):
                                with patch.object(sim_runner, "VENUE_QUOTES_FILE", quotes_path):
                                    with patch.object(sim_runner, "FUNDING_HISTORY_FILE", funding_path):
                                        with patch.object(sim_runner, "TICK_FEATURES", tick_features_path):
                                            with patch.object(sim_runner, "CROSS_EXCHANGE_FILE", cross_exchange_path):
                                                with patch.object(sim_runner, "FUNDING_SNAPSHOT_FILE", funding_snapshot_path):
                                                    with patch.object(
                                                        sim_runner,
                                                        "get_itc_signal",
                                                        return_value={"reason": "ok", "signal": {"metrics": {"sentiment": 0.4}, "source": "test"}},
                                                    ):
                                                        sim_runner.run(full=True, config_path=config_path, features_path=features_path)

            state_path = root / "sim" / "SIM_C" / "state.json"
            model_state_path = root / "sim" / "SIM_C" / "model_state.json"
            trades_path = root / "sim" / "SIM_C" / "trades.jsonl"
            metrics_path = root / "sim" / "SIM_C" / "metrics.json"
            performance_path = root / "sim" / "SIM_C" / "performance.json"
            prediction_events_path = root / "sim" / "SIM_C" / "prediction_events.jsonl"
            self.assertTrue(state_path.exists())
            self.assertTrue(model_state_path.exists())
            self.assertTrue(trades_path.exists())
            self.assertTrue(metrics_path.exists())
            self.assertTrue(performance_path.exists())
            self.assertTrue(prediction_events_path.exists())
            self.assertIn('"BTCUSDT"', model_state_path.read_text(encoding="utf-8"))
            self.assertIn('"directional_accuracy"', metrics_path.read_text(encoding="utf-8"))
            self.assertIn('"total_fees_usd"', performance_path.read_text(encoding="utf-8"))
            self.assertIn('"forecast_issued"', prediction_events_path.read_text(encoding="utf-8"))
            self.assertGreater(len(trades_path.read_text(encoding="utf-8").strip().splitlines()), 0)

    def test_close_execution_uses_position_notional_not_current_equity(self):
        cfg = {
            "id": "SIM_COSTS",
            "strategy": "ensemble_competing_models_long_flat",
            "universe": ["BTCUSDT"],
            "capital": 1000.0,
            "dd_kill": 0.5,
            "daily_loss": 0.5,
            "max_trades_per_day": 20,
            "execution": {
                "max_notional_pct": 0.1,
                "fee_rate": 0.001,
                "slippage_bps": 0.0,
                "spread_bps": 0.0,
                "market_impact_bps_per_10k": 0.0,
                "funding_bps_8h": 0.0,
                "borrow_bps_daily": 0.0,
            },
        }

        with tempfile.TemporaryDirectory() as td:
            with patch.object(sim_runner, "BASE_DIR", Path(td)):
                sim = sim_runner.Sim(cfg)
                open_trade = sim._execute("BTCUSDT", "open_long", 100.0, 0, "test_open")
                self.assertIsNotNone(open_trade)
                sim.equity = 5000.0
                close_trade = sim._execute("BTCUSDT", "close_long", 100.0, 900000, "test_close")

        self.assertIsNotNone(close_trade)
        self.assertAlmostEqual(close_trade["size_usd"], 100.0, places=6)
        self.assertAlmostEqual(close_trade["cost_components"]["fee_usd"], 0.1, places=6)

    def test_run_uses_recent_candle_window_for_competing_models(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            market_dir = root / "market"
            market_dir.mkdir(parents=True, exist_ok=True)
            config_path = root / "system1_trading.yaml"
            config_path.write_text(
                "sims:\n"
                "  - id: SIM_C\n"
                "    strategy: ensemble_competing_models_long_flat\n"
                "    universe:\n"
                "      - BTCUSDT\n"
                "    capital: 1000\n"
                "    dd_kill: 0.15\n"
                "    daily_loss: 0.05\n"
                "    max_trades_per_day: 8\n",
                encoding="utf-8",
            )
            features_path = root / "system1_trading.features.yaml"
            features_path.write_text("features:\n  competing_models: true\n", encoding="utf-8")

            candles_15m = market_dir / "candles_15m.jsonl"
            candles_1h = market_dir / "candles_1h.jsonl"
            ticks_path = market_dir / "ticks.jsonl"
            quotes_path = market_dir / "venue_quotes.jsonl"
            funding_path = market_dir / "funding_rates.jsonl"
            tick_features_path = market_dir / "tick_features.json"
            cross_exchange_path = market_dir / "cross_exchange_features.json"
            funding_snapshot_path = market_dir / "funding_snapshot.json"
            ticks_path.write_text("", encoding="utf-8")
            quotes_path.write_text("", encoding="utf-8")
            funding_path.write_text("", encoding="utf-8")
            tick_features_path.write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            cross_exchange_path.write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            funding_snapshot_path.write_text('{"version":1,"generated_at":0,"symbols":{}}\n', encoding="utf-8")
            with candles_15m.open("w", encoding="utf-8") as handle:
                for idx in range(150):
                    close = 100.0 + (idx * 0.25)
                    ts = idx * 900000
                    handle.write(
                        (
                            '{"symbol":"BTCUSDT","ts":%d,"o":%.4f,"h":%.4f,"l":%.4f,"c":%.4f,"v":1.0}\n'
                            % (ts, close - 0.2, close + 0.4, close - 0.5, close)
                        )
                    )
            with candles_1h.open("w", encoding="utf-8") as handle:
                for idx in range(50):
                    close = 100.0 + (idx * 1.0)
                    ts = idx * 3600000
                    handle.write(
                        (
                            '{"symbol":"BTCUSDT","ts":%d,"o":%.4f,"h":%.4f,"l":%.4f,"c":%.4f,"v":1.0}\n'
                            % (ts, close - 0.4, close + 0.6, close - 0.7, close)
                        )
                    )

            window_observations = []

            def fake_run_bar(self, symbol, bar, closes, sentiment_score, candles_window, htf_bullish=None, tick_snapshot=None, params=None):
                window_observations.append(
                    {
                        "bar_ts": bar["ts"],
                        "window_len": len(candles_window),
                        "window_last_ts": candles_window[-1]["ts"] if candles_window else None,
                        "tick_snapshot": tick_snapshot,
                    }
                )
                return [], {
                    "signal": 0.0,
                    "confidence": 0.0,
                    "risk_state": "normal",
                    "risk_signal": 0.0,
                    "walk_forward": {"updated": False, "realized_return": 0.0},
                    "leaderboard": [],
                }

            with patch.object(sim_runner, "BASE_DIR", root):
                with patch.object(sim_runner, "REPO_ROOT", root):
                    with patch.object(sim_runner, "CANDLES_15M", candles_15m):
                        with patch.object(sim_runner, "CANDLES_1H", candles_1h):
                            with patch.object(sim_runner, "TICKS_FILE", ticks_path):
                                with patch.object(sim_runner, "VENUE_QUOTES_FILE", quotes_path):
                                    with patch.object(sim_runner, "FUNDING_HISTORY_FILE", funding_path):
                                        with patch.object(sim_runner, "TICK_FEATURES", tick_features_path):
                                            with patch.object(sim_runner, "CROSS_EXCHANGE_FILE", cross_exchange_path):
                                                with patch.object(sim_runner, "FUNDING_SNAPSHOT_FILE", funding_snapshot_path):
                                                    with patch.object(sim_runner, "get_itc_signal", return_value={"reason": "missing"}):
                                                        with patch.object(sim_runner.Sim, "run_bar_with_competing_models", new=fake_run_bar):
                                                            sim_runner.run(full=True, config_path=config_path, features_path=features_path)

            self.assertTrue(window_observations)
            last = window_observations[-1]
            self.assertEqual(last["window_last_ts"], last["bar_ts"])
            self.assertEqual(last["window_len"], 128)
            self.assertIsNone(last["tick_snapshot"])


if __name__ == "__main__":
    unittest.main()
