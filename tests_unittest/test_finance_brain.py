import json
import tempfile
import unittest
from pathlib import Path

from core_infra import finance_brain


class FinanceBrainTests(unittest.TestCase):
    def test_load_external_signal_marks_aged_ok_payload_as_stale(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "macbook_sentiment.json"
            target.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "generated_at": "2026-03-10T10:15:41Z",
                        "poll": {"stale_after_seconds": 60},
                        "model": {"requested": "phi4-mini", "resolved": "phi4-mini:latest"},
                        "aggregate": {"sentiment": 0.17, "confidence": 0.7, "risk_on": 0.52, "risk_off": 0.29},
                    }
                ),
                encoding="utf-8",
            )

            payload = finance_brain.load_external_signal(target)

            self.assertEqual(payload["status"], "stale")
            self.assertEqual(payload["status_raw"], "ok")
            self.assertTrue(payload["stale"])
            self.assertEqual(payload["stale_after_seconds"], 60)

    def test_combine_external_inputs_ignores_missing_sources(self):
        combined = finance_brain.combine_external_inputs(
            {
                "macbook_sentiment": {
                    "status": "ok",
                    "producer": "c_lawd",
                    "model_resolved": "phi4-mini:latest",
                    "aggregate": {
                        "sentiment": 0.2,
                        "confidence": 0.7,
                        "risk_on": 0.55,
                        "risk_off": 0.25,
                    },
                },
                "fingpt_sentiment": {
                    "status": "missing",
                    "producer": "fingpt",
                    "model_resolved": None,
                    "aggregate": {},
                },
            }
        )

        self.assertEqual(combined["status"], "ok")
        self.assertEqual(combined["sources"]["fingpt_sentiment"]["weight"], 0.0)
        self.assertAlmostEqual(combined["sentiment"], 0.2, places=4)
        self.assertEqual(combined["models_resolved"], {"macbook_sentiment": "phi4-mini:latest"})

    def test_combine_external_inputs_uses_fallback_only_when_macbook_not_fresh(self):
        combined = finance_brain.combine_external_inputs(
            {
                "macbook_sentiment": {
                    "status": "stale",
                    "producer": "c_lawd",
                    "model_resolved": "phi4-mini:latest",
                    "aggregate": {
                        "sentiment": 0.2,
                        "confidence": 0.7,
                        "risk_on": 0.55,
                        "risk_off": 0.25,
                    },
                },
                "fingpt_sentiment": {
                    "status": "ok",
                    "producer": "dali",
                    "model_resolved": "local-assistant",
                    "aggregate": {
                        "sentiment": -0.11,
                        "confidence": 0.61,
                        "risk_on": 0.2,
                        "risk_off": 0.42,
                    },
                },
            }
        )

        self.assertEqual(combined["status"], "ok")
        self.assertEqual(combined["sources"]["macbook_sentiment"]["weight"], 0.0)
        self.assertGreater(combined["sources"]["fingpt_sentiment"]["weight"], 0.0)
        self.assertEqual(combined["models_resolved"], {"macbook_sentiment": "phi4-mini:latest", "fingpt_sentiment": "local-assistant"})

    def test_extract_json_object_handles_reasoning_wrappers(self):
        text = '<think>hidden</think>\n{"bias":0.14,"confidence":0.61,"weight_overrides":{"microstructure":0.8},"note":"ok"}'
        parsed = finance_brain._extract_json_object(text)
        self.assertEqual(parsed["bias"], 0.14)
        self.assertEqual(parsed["weight_overrides"]["microstructure"], 0.8)

    def test_evaluate_symbol_separates_inputs_from_learned_weights(self):
        external_inputs = {
            "macbook_sentiment": {
                "status": "ok",
                "producer": "c_lawd",
                "model_resolved": "phi4-mini:latest",
                "aggregate": {
                    "sentiment": 0.24,
                    "confidence": 0.72,
                    "risk_on": 0.55,
                    "risk_off": 0.21,
                },
            },
            "fingpt_sentiment": {
                "status": "ok",
                "producer": "fingpt",
                "model_resolved": "FinGPT/fingpt-sentiment_llama2-13b_lora",
                "aggregate": {
                    "sentiment": 0.31,
                    "confidence": 0.66,
                    "risk_on": 0.61,
                    "risk_off": 0.18,
                },
            },
        }
        closes = [100.0 + (idx * 0.4) for idx in range(64)]
        result = finance_brain.evaluate_symbol(
            symbol="BTCUSDT",
            ts=1773138480000,
            closes=closes,
            htf_bullish=True,
            itc_sentiment=0.18,
            tick_snapshot={
                "trade_count": 320,
                "imbalance": 0.22,
                "momentum_1m": 0.0008,
                "window_return": 0.0012,
                "spread_bps": 0.9,
                "realized_vol": 0.00009,
            },
            cross_exchange_row={"mid_gap_bps": 0.4},
            funding_row={"last_funding_rate": 0.00002},
            external_inputs=external_inputs,
            retrieval_stats={"sample_size": 8, "win_rate": 0.64, "avg_pnl": 0.14, "recent_bias": 0.18},
            params={"llm_enabled": False},
            allow_llm=False,
        )

        self.assertIn("incoming_source_scores", result)
        self.assertIn("learned_weights", result)
        self.assertAlmostEqual(result["incoming_source_scores"]["macbook_sentiment"], 0.24, places=4)
        self.assertIn("external_sources", result["incoming_source_scores"])
        self.assertIsNone(result["decision"]["model_resolved"])
        self.assertEqual(result["decision"]["sentiment_model_resolved"], "phi4-mini:latest")
        self.assertEqual(
            result["decision"]["sentiment_models_resolved"]["fingpt_sentiment"],
            "FinGPT/fingpt-sentiment_llama2-13b_lora",
        )
        self.assertIn("sentiment", result["learned_weights"])
        self.assertNotIn("macbook_sentiment", result["learned_weights"])
        self.assertIn(result["decision"]["action"], {"buy", "hold", "flat"})

    def test_call_local_llm_tracks_requested_and_resolved_analysis_model(self):
        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "model": "local-assistant",
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "bias": 0.16,
                                            "confidence": 0.67,
                                            "weight_overrides": {"technical": 1.3},
                                            "note": "trend still dominates",
                                        }
                                    )
                                }
                            }
                        ],
                    }
                ).encode("utf-8")

        with unittest.mock.patch("core_infra.finance_brain.request.urlopen", return_value=_Response()):
            result = finance_brain._call_local_llm(
                "BTCUSDT",
                {"agents": {}, "weights": {}, "risk_state": "normal"},
                {"llm_model": "local-assistant", "llm_base_url": "http://127.0.0.1:8001/v1"},
            )

        self.assertTrue(result["used"])
        self.assertEqual(result["model_requested"], "local-assistant")
        self.assertEqual(result["model_resolved"], "local-assistant")

    def test_build_live_snapshot_writes_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact_path = root / "finance" / "consensus_latest.json"
            history_path = root / "finance" / "consensus_history.jsonl"
            external_path = root / "external" / "macbook_sentiment.json"
            external_path.parent.mkdir(parents=True, exist_ok=True)
            external_path.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "producer": "c_lawd",
                        "generated_at": "2026-03-10T10:15:41Z",
                        "model": {"requested": "phi4-mini", "resolved": "phi4-mini:latest", "fallback_used": False},
                        "aggregate": {"sentiment": 0.17, "confidence": 0.7, "risk_on": 0.52, "risk_off": 0.29},
                    }
                ),
                encoding="utf-8",
            )
            fingpt_path = root / "external" / "fingpt_sentiment.json"
            fingpt_path.parent.mkdir(parents=True, exist_ok=True)
            fingpt_path.write_text(
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
                        "aggregate": {"sentiment": 0.21, "confidence": 0.64, "risk_on": 0.57, "risk_off": 0.2},
                    }
                ),
                encoding="utf-8",
            )
            candles = {
                "BTCUSDT": [
                    {"ts": idx * 900000, "c": 100.0 + (idx * 0.45)}
                    for idx in range(80)
                ]
            }
            payload = finance_brain.build_live_snapshot(
                candles_15m=candles,
                htf_regime={"BTCUSDT": {(79 * 900000 // 3600000) * 3600000: True}},
                tick_features={
                    "BTCUSDT": {
                        "trade_count": 420,
                        "imbalance": 0.16,
                        "momentum_1m": 0.0007,
                        "window_return": 0.001,
                        "spread_bps": 0.8,
                        "realized_vol": 0.00008,
                    }
                },
                cross_exchange_snapshot={"symbols": {"BTCUSDT": {"mid_gap_bps": 0.32}}},
                funding_snapshot={"symbols": {"BTCUSDT": {"last_funding_rate": 0.00003}}},
                symbols=["BTCUSDT"],
                itc_sentiment_by_hour={0: 0.1, (79 * 900000 // 3600000) * 3600000: 0.1},
                params={
                    "llm_enabled": False,
                    "artifact_path": str(artifact_path),
                    "history_path": str(history_path),
                    "external_signal_path": str(external_path),
                    "fingpt_signal_path": str(fingpt_path),
                    "sim_root": str(root / "sim"),
                },
            )

            self.assertTrue(artifact_path.exists())
            self.assertTrue(history_path.exists())
            self.assertEqual(payload["external_signal"]["inputs"]["macbook_sentiment"]["model_resolved"], "phi4-mini:latest")
            self.assertEqual(
                payload["external_signal"]["inputs"]["fingpt_sentiment"]["model_resolved"],
                "FinGPT/fingpt-sentiment_llama2-13b_lora",
            )
            self.assertIn("BTCUSDT", payload["symbols"])

    def test_build_retrieval_stats_can_filter_to_active_sim_ids(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active = root / "sim" / "SIM_H"
            frozen = root / "sim" / "SIM_D"
            active.mkdir(parents=True, exist_ok=True)
            frozen.mkdir(parents=True, exist_ok=True)
            (active / "trades.jsonl").write_text(
                json.dumps(
                    {
                        "symbol": "BTCUSDT",
                        "side": "close_long",
                        "pnl": 12.0,
                        "reason": "active_edge",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (frozen / "trades.jsonl").write_text(
                json.dumps(
                    {
                        "symbol": "BTCUSDT",
                        "side": "close_long",
                        "pnl": -10.0,
                        "reason": "frozen_failure",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            filtered = finance_brain.build_retrieval_stats(["BTCUSDT"], sim_root=root / "sim", sim_ids=["SIM_H"], limit=8)

            self.assertEqual(filtered["BTCUSDT"]["sample_size"], 1)
            self.assertIn("active_edge", filtered["BTCUSDT"]["last_reasons"])
            self.assertNotIn("frozen_failure", filtered["BTCUSDT"]["last_reasons"])


if __name__ == "__main__":
    unittest.main()
