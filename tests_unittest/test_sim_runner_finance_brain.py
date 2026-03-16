import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sim_runner


class SimRunnerFinanceBrainTests(unittest.TestCase):
    def test_sim_h_writes_finance_snapshot_and_trades(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            market_dir = root / "market"
            market_dir.mkdir(parents=True, exist_ok=True)
            external_dir = root / "workspace" / "state" / "external"
            external_dir.mkdir(parents=True, exist_ok=True)
            (external_dir / "macbook_sentiment.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "producer": "c_lawd",
                        "generated_at": "2026-03-10T10:15:41Z",
                        "model": {"requested": "phi4-mini", "resolved": "phi4-mini:latest", "fallback_used": False},
                        "aggregate": {"sentiment": 0.22, "confidence": 0.74, "risk_on": 0.58, "risk_off": 0.24},
                    }
                ),
                encoding="utf-8",
            )
            (external_dir / "fingpt_sentiment.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "producer": "fingpt",
                        "generated_at": "2026-03-10T10:16:00Z",
                        "model": {
                            "requested": "FinGPT sentiment",
                            "resolved": "FinGPT/fingpt-sentiment_llama2-13b_lora",
                            "fallback_used": False,
                        },
                        "aggregate": {"sentiment": 0.19, "confidence": 0.63, "risk_on": 0.56, "risk_off": 0.22},
                    }
                ),
                encoding="utf-8",
            )

            config_path = root / "system1_trading.yaml"
            config_path.write_text(
                "sims:\n"
                "  - id: SIM_H\n"
                "    strategy: latency_consensus_long_flat\n"
                "    universe:\n"
                "      - BTCUSDT\n"
                "    capital: 1000\n"
                "    dd_kill: 0.15\n"
                "    daily_loss: 0.05\n"
                "    max_trades_per_day: 8\n",
                encoding="utf-8",
            )
            features_path = root / "system1_trading.features.yaml"
            features_path.write_text(
                "features:\n"
                "  finance_brain: true\n"
                "features_params:\n"
                "  finance_brain:\n"
                "    enabled: true\n"
                "    llm_enabled: false\n"
                f"    artifact_path: {root / 'workspace' / 'artifacts' / 'finance' / 'consensus_latest.json'}\n"
                f"    history_path: {root / 'workspace' / 'artifacts' / 'finance' / 'consensus_history.jsonl'}\n"
                f"    external_signal_path: {external_dir / 'macbook_sentiment.json'}\n"
                f"    fingpt_signal_path: {external_dir / 'fingpt_sentiment.json'}\n"
                f"    sim_root: {root / 'sim'}\n",
                encoding="utf-8",
            )

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
            tick_features_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "generated_at": 0,
                        "symbols": {
                            "BTCUSDT": {
                                "trade_count": 420,
                                "imbalance": 0.18,
                                "momentum_1m": 0.0007,
                                "window_return": 0.0011,
                                "spread_bps": 0.9,
                                "realized_vol": 0.00008,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            cross_exchange_path.write_text(
                json.dumps({"version": 1, "generated_at": 0, "symbols": {"BTCUSDT": {"mid_gap_bps": 0.31}}}),
                encoding="utf-8",
            )
            funding_snapshot_path.write_text(
                json.dumps({"version": 1, "generated_at": 0, "symbols": {"BTCUSDT": {"last_funding_rate": 0.00003}}}),
                encoding="utf-8",
            )

            with candles_15m.open("w", encoding="utf-8") as handle:
                for idx in range(96):
                    close = 100.0 + (idx * 0.42)
                    handle.write(
                        '{"symbol":"BTCUSDT","ts":%d,"o":%.4f,"h":%.4f,"l":%.4f,"c":%.4f,"v":1.0}\n'
                        % (idx * 900000, close - 0.2, close + 0.4, close - 0.4, close)
                    )
            with candles_1h.open("w", encoding="utf-8") as handle:
                for idx in range(36):
                    close = 100.0 + (idx * 1.5)
                    handle.write(
                        '{"symbol":"BTCUSDT","ts":%d,"o":%.4f,"h":%.4f,"l":%.4f,"c":%.4f,"v":1.0}\n'
                        % (idx * 3600000, close - 0.3, close + 0.5, close - 0.5, close)
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
                                                    sim_runner.run(full=True, config_path=config_path, features_path=features_path)

            trades_path = root / "sim" / "SIM_H" / "trades.jsonl"
            snapshot_path = root / "workspace" / "artifacts" / "finance" / "consensus_latest.json"
            self.assertTrue(trades_path.exists())
            self.assertTrue(snapshot_path.exists())
            self.assertGreater(len(trades_path.read_text(encoding="utf-8").strip().splitlines()), 0)
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["external_signal"]["inputs"]["macbook_sentiment"]["model_resolved"], "phi4-mini:latest")
            self.assertEqual(
                snapshot["external_signal"]["inputs"]["fingpt_sentiment"]["model_resolved"],
                "FinGPT/fingpt-sentiment_llama2-13b_lora",
            )
            self.assertIn("BTCUSDT", snapshot["symbols"])


if __name__ == "__main__":
    unittest.main()
