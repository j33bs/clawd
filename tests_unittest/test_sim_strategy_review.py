import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import sim_review  # noqa: E402


class SimStrategyReviewTests(unittest.TestCase):
    def test_build_review_tracks_free_signal_and_weekly_x_cadence(self):
        now = datetime.now(timezone.utc)
        weekly_x_generated_at = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        fresh_signal_at = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            weekly_x_path = root / "weekly_x_strategy_review.json"
            weekly_x_path.write_text(
                (
                    "{\n"
                    f'  "generated_at": "{weekly_x_generated_at}",\n'
                    '  "producer": "c_lawd",\n'
                    '  "summary": "Bias crypto sleeves toward catalyst breakouts for the week."\n'
                    "}"
                ),
                encoding="utf-8",
            )
            sims = [
                {
                    "id": "SIM_B",
                    "display_name": "Legacy ITC Tilt",
                    "bucket": "Legacy",
                    "thesis": "15m bar model with ITC sentiment tilt",
                    "status_note": "AU-portable paper signal lane",
                    "active_book": True,
                    "live_equity_change": -0.65,
                    "live_return_pct": -0.07,
                    "net_equity_change": -0.83,
                    "net_return_pct": -0.08,
                    "fees_usd": 1.5,
                    "fee_drag": True,
                    "round_trips": 14,
                    "win_rate": 33.3,
                    "open_positions": 2,
                    "updated_at": "2026-03-15T00:20:00Z",
                },
                {
                    "id": "SIM_H",
                    "display_name": "LOAR Consensus",
                    "bucket": "LOAR",
                    "thesis": "Local orderflow-assisted reasoning manager/bias layer",
                    "status_note": "Bias layer",
                    "active_book": True,
                    "live_equity_change": -0.2,
                    "live_return_pct": -0.02,
                    "net_equity_change": -0.2,
                    "net_return_pct": -0.02,
                    "fees_usd": 0.2,
                    "fee_drag": False,
                    "round_trips": 8,
                    "win_rate": 50.0,
                    "open_positions": 0,
                    "updated_at": "2026-03-15T00:20:00Z",
                },
            ]
            finance_brain = {
                "external_signal": {
                    "inputs": {
                        "macbook_sentiment": {
                            "status": "ok",
                            "producer": "c_lawd",
                            "model_resolved": "phi4-mini:latest",
                            "generated_at": fresh_signal_at,
                        }
                    }
                }
            }
            trading_strategy = {"integration": {"notes": ["Map to Kraken spot pairs before live cutover."]}}

            with patch.object(sim_review, "WEEKLY_X_STRATEGY_PATHS", (weekly_x_path,)):
                payload = sim_review.build_sim_strategy_review(sims, finance_brain, trading_strategy, review_interval_hours=6)

            self.assertEqual(payload["status"], "active")
            self.assertTrue(payload["free_realtime_signal"]["ready"])
            self.assertEqual(payload["weekly_x_review"]["status"], "fresh")
            self.assertEqual(payload["summary"]["active_count"], 2)
            self.assertEqual(payload["summary"]["retune_count"], 1)
            self.assertEqual(payload["summary"]["keep_count"], 1)
            self.assertEqual(payload["recommendations"][0]["id"], "SIM_B")
            self.assertEqual(payload["recommendations"][0]["recommendation"], "retune")
            self.assertEqual(payload["recommendations"][1]["id"], "SIM_H")
            self.assertEqual(payload["recommendations"][1]["recommendation"], "keep")

    def test_build_review_marks_stale_free_signal_as_limited(self):
        stale_signal_at = (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sims = [
            {
                "id": "SIM_E",
                "display_name": "Crypto Reversion Grid",
                "bucket": "CBP",
                "thesis": "Crypto reversion lane",
                "status_note": "AU-portable paper lane",
                "active_book": True,
                "live_equity_change": -0.3,
                "live_return_pct": -0.03,
                "fees_usd": 0.4,
                "fee_drag": False,
                "round_trips": 6,
                "win_rate": 50.0,
                "open_positions": 0,
                "updated_at": "2026-03-15T00:20:00Z",
            }
        ]
        finance_brain = {
            "external_signal": {
                "inputs": {
                        "macbook_sentiment": {
                            "status": "ok",
                            "producer": "c_lawd",
                            "model_resolved": "phi4-mini:latest",
                            "generated_at": stale_signal_at,
                        }
                    }
                }
            }

        payload = sim_review.build_sim_strategy_review(sims, finance_brain, trading_strategy={})

        self.assertFalse(payload["free_realtime_signal"]["ready"])
        self.assertEqual(payload["free_realtime_signal"]["status"], "stale")
        self.assertTrue(payload["free_realtime_signal"]["stale"])

    def test_build_review_uses_dali_fallback_when_macbook_is_stale(self):
        now = datetime.now(timezone.utc)
        stale_signal_at = (now - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
        fresh_fallback_at = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sims = [
            {
                "id": "SIM_H",
                "display_name": "LOAR Consensus",
                "bucket": "LOAR",
                "thesis": "Local orderflow-assisted reasoning manager/bias layer",
                "status_note": "Bias layer",
                "active_book": True,
                "live_equity_change": 0.2,
                "live_return_pct": 0.02,
                "fees_usd": 0.2,
                "fee_drag": False,
                "round_trips": 8,
                "win_rate": 50.0,
                "open_positions": 0,
                "updated_at": "2026-03-15T00:20:00Z",
            }
        ]
        finance_brain = {
            "external_signal": {
                "inputs": {
                    "macbook_sentiment": {
                        "status": "stale",
                        "producer": "c_lawd",
                        "model_resolved": "phi4-mini:latest",
                        "generated_at": stale_signal_at,
                    },
                    "fingpt_sentiment": {
                        "status": "ok",
                        "producer": "dali",
                        "model_resolved": "local-assistant",
                        "generated_at": fresh_fallback_at,
                    },
                }
            }
        }

        payload = sim_review.build_sim_strategy_review(sims, finance_brain, trading_strategy={})

        self.assertTrue(payload["free_realtime_signal"]["ready"])
        self.assertEqual(payload["free_realtime_signal"]["active_source_id"], "fingpt_sentiment")
        self.assertEqual(payload["free_realtime_signal"]["producer"], "dali")
        self.assertEqual(payload["free_realtime_signal"]["model_resolved"], "local-assistant")

    def test_build_review_keeps_fallback_candidate_actionable(self):
        sims = [
            {
                "id": "SIM_I",
                "display_name": "US Equity Event Impulse",
                "bucket": "5.4 Pro",
                "thesis": "Alpaca event impulse sleeve",
                "status_note": "paper live on public bars",
                "active_book": True,
                "stage": "paper_live",
                "strategy_role": "candidate",
                "continuous_improvement": True,
                "improvement_focus": "Event classifier precision",
                "data_dependency": "alpaca_equities_news",
                "target_venue": "Alpaca",
                "live_equity_change": 0.0,
                "live_return_pct": 0.0,
                "fees_usd": 0.0,
                "fee_drag": False,
                "round_trips": 0,
                "win_rate": 0.0,
                "open_positions": 0,
                "updated_at": "2026-03-15T00:20:00Z",
            }
        ]
        finance_brain = {"external_signal": {"inputs": {}}}

        payload = sim_review.build_sim_strategy_review(sims, finance_brain, trading_strategy={})
        row = payload["recommendations"][0]

        self.assertEqual(row["stage"], "paper_live")
        self.assertEqual(row["recommendation"], "keep")
        self.assertTrue(any("upgrade to alpaca equities news" in action for action in row["actions"]))
        self.assertEqual(row["improvement_focus"], "Event classifier precision")


if __name__ == "__main__":
    unittest.main()
