import tempfile
import unittest
from pathlib import Path

from core_infra.competing_models import (
    ensure_symbol_state,
    issue_predictions,
    load_model_state,
    run_competing_models,
    save_model_state,
    score_pending_predictions,
    summarize_prediction_metrics,
    update_walk_forward_scores,
)


class CompetingModelsTests(unittest.TestCase):
    def test_walk_forward_rewards_correct_model_direction(self):
        state = {"version": 1, "symbols": {}}
        symbol_state = ensure_symbol_state(state, "BTCUSDT")
        symbol_state["last_close"] = 100.0
        symbol_state["last_ts"] = 1000
        symbol_state["last_signals"] = {
            "trend_follow": {"signal": 0.8, "confidence": 1.0, "weight": 1.0},
            "risk_guard": {"signal": -0.6, "confidence": 1.0, "weight": 1.0},
        }

        out = update_walk_forward_scores(symbol_state, current_close=105.0, current_ts=2000)
        self.assertTrue(out["updated"])
        trend = symbol_state["models"]["trend_follow"]
        risk = symbol_state["models"]["risk_guard"]
        self.assertGreater(trend["score_ewma"], 0.0)
        self.assertLess(risk["score_ewma"], 0.0)
        self.assertEqual(trend["hits"], 1)
        self.assertEqual(risk["misses"], 1)

    def test_run_competing_models_persists_last_signals_and_leaderboard(self):
        state = {"version": 1, "symbols": {}}
        symbol_state = ensure_symbol_state(state, "BTCUSDT")
        closes = [100 + i for i in range(40)]
        candles = [
            {"symbol": "BTCUSDT", "ts": i * 900000, "o": 99 + i, "h": 101 + i, "l": 98 + i, "c": 100 + i}
            for i in range(40)
        ]
        out = run_competing_models(
            symbol_state=symbol_state,
            ts=candles[-1]["ts"],
            closes=closes,
            candles=candles,
            sentiment_score=0.35,
            htf_bullish=True,
            include_sentiment=True,
            tick_snapshot={
                "trade_count": 64,
                "imbalance": 0.45,
                "window_return": 0.003,
                "momentum_1m": 0.002,
                "spread_bps": 2.5,
            },
        )
        self.assertIn("leaderboard", out)
        self.assertGreater(len(out["items"]), 2)
        self.assertTrue(symbol_state["last_signals"])
        self.assertEqual(symbol_state["last_close"], closes[-1])
        self.assertIn("tick_microstructure", symbol_state["last_signals"])

    def test_model_state_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "model_state.json"
            state = {"version": 1, "symbols": {"ETHUSDT": {"last_close": 12.3, "models": {}}}}
            save_model_state(path, state)
            loaded = load_model_state(path)
        self.assertEqual(loaded["symbols"]["ETHUSDT"]["last_close"], 12.3)

    def test_prediction_issue_and_score_updates_metrics(self):
        state = {"version": 1, "symbols": {}}
        symbol_state = ensure_symbol_state(state, "BTCUSDT")
        issued = issue_predictions(
            symbol_state,
            ts=1000,
            close=100.0,
            signal=0.8,
            confidence=0.5,
            top_model="trend_follow",
            horizon_bars=[1],
            bar_ms=100,
        )
        self.assertEqual(len(issued), 1)
        settled = score_pending_predictions(symbol_state, current_close=102.0, current_ts=1100)
        self.assertEqual(len(settled), 1)
        metrics = summarize_prediction_metrics(symbol_state)
        self.assertEqual(metrics["count"], 1)
        self.assertGreater(metrics["directional_accuracy"], 0.0)
        self.assertGreaterEqual(metrics["mean_brier"], 0.0)


if __name__ == "__main__":
    unittest.main()
