import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workspace.market_sentiment import producer
from workspace.market_sentiment.classifier import ClassifierRuntime
from workspace.market_sentiment.sources import SourceData


class TestMarketSentimentProducer(unittest.TestCase):
    def test_load_openclaw_env_vars_reads_string_values_from_config_files(self):
        with tempfile.TemporaryDirectory() as td:
            home_cfg = Path(td) / "home-openclaw.json"
            repo_cfg = Path(td) / "repo-openclaw.json"
            home_cfg.write_text('{"env":{"vars":{"COINGECKO_API_KEY":"demo-key"}}}\n', encoding="utf-8")
            repo_cfg.write_text('{"env":{"vars":{"OTHER_KEY":"other-value"}}}\n', encoding="utf-8")
            with mock.patch.object(producer, "OPENCLAW_ENV_CONFIG_PATHS", (home_cfg, repo_cfg)):
                with mock.patch.dict(os.environ, {}, clear=True):
                    producer._load_openclaw_env_vars()
                    self.assertEqual(os.environ["COINGECKO_API_KEY"], "demo-key")
                    self.assertEqual(os.environ["OTHER_KEY"], "other-value")

    def test_run_market_sentiment_persists_snapshot_artifact_once(self):
        class _FakeSource:
            def fetch(self, _session):
                return SourceData(
                    name="fear_greed",
                    optional=False,
                    weight_hint=1.0,
                    status="ok",
                    fetched_at="2026-03-10T12:00:00Z",
                    url="https://example.com/fng",
                    raw_content=b'{"data":[]}',
                    raw_extension="json",
                    transport={"url": "https://example.com/fng", "http_status": 200},
                    metrics={"fear_greed_value": 50.0},
                    heuristic={
                        "sentiment": 0.1,
                        "confidence": 0.5,
                        "risk_on": 0.55,
                        "risk_off": 0.45,
                        "regime": "neutral",
                        "drivers": ["balanced"],
                    },
                    summary="Fear & Greed index is 50.",
                )

        class _FakeClassifier:
            def __init__(self, *args, **kwargs):
                pass

            def classify(self, **kwargs):
                return (
                    {
                        "sentiment": 0.2,
                        "confidence": 0.7,
                        "risk_on": 0.6,
                        "risk_off": 0.2,
                        "regime": "risk_on",
                        "drivers": ["driver-a"],
                    },
                    {
                        "provider": "ollama",
                        "requested": "phi4-mini",
                        "resolved": "phi4-mini:latest",
                        "fallback_used": False,
                        "status": "ok",
                        "error": None,
                        "latency_ms": 12,
                    },
                )

            def runtime(self):
                return ClassifierRuntime(
                    provider="ollama",
                    requested="phi4-mini",
                    resolved="phi4-mini:latest",
                    fallback_used=False,
                    status="ok",
                )

        config = {
            "poll": {"recommended_interval_seconds": 900, "stale_after_seconds": 2700},
            "model": {
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434",
                "requested": "phi4-mini",
                "fallbacks": ["phi3:mini"],
                "keep_alive": "0s",
            },
            "delivery": {"enabled": False},
        }

        with tempfile.TemporaryDirectory() as td:
            output_path = Path(td) / "macbook_sentiment.json"
            persist_calls = []

            def _persist_snapshot(snapshot, artifact_root):
                persist_calls.append(snapshot["artifacts"]["snapshot_ref"])
                return "workspace/artifacts/market_sentiment/normalized/2026/03/10/market_sentiment_20260310T120000Z_deadbeef.json"

            with mock.patch.object(producer, "_load_config", return_value=config), \
                mock.patch.object(producer, "_load_openclaw_env_vars"), \
                mock.patch.object(producer, "build_sources", return_value=[_FakeSource()]), \
                mock.patch.object(producer, "OllamaMarketClassifier", _FakeClassifier), \
                mock.patch.object(producer, "utc_now_iso", return_value="2026-03-10T12:00:00Z"), \
                mock.patch.object(producer, "emit_event"), \
                mock.patch.object(producer, "persist_raw_artifact", return_value="workspace/artifacts/market_sentiment/raw/2026/03/10/fear_greed_20260310T120000Z_deadbeef.json"), \
                mock.patch.object(producer, "persist_snapshot_artifact", side_effect=_persist_snapshot), \
                mock.patch.object(producer, "deliver_snapshot") as deliver_mock:
                snapshot = producer.run_market_sentiment(output_path=output_path)

            deliver_mock.assert_called_once()
            self.assertEqual(len(persist_calls), 1)
            self.assertEqual(persist_calls[0], "pending://snapshot_ref")
            self.assertEqual(
                snapshot["artifacts"]["snapshot_ref"],
                "workspace/artifacts/market_sentiment/normalized/2026/03/10/market_sentiment_20260310T120000Z_deadbeef.json",
            )
            self.assertTrue(output_path.is_file())

    def test_run_market_sentiment_degrades_to_heuristic_when_idle_gate_blocks_phi4(self):
        class _FakeSource:
            def fetch(self, _session):
                return SourceData(
                    name="fear_greed",
                    optional=False,
                    weight_hint=1.0,
                    status="ok",
                    fetched_at="2026-03-10T12:00:00Z",
                    url="https://example.com/fng",
                    raw_content=b'{"data":[]}',
                    raw_extension="json",
                    transport={"url": "https://example.com/fng", "http_status": 200},
                    metrics={"fear_greed_value": 50.0},
                    heuristic={
                        "sentiment": 0.1,
                        "confidence": 0.5,
                        "risk_on": 0.55,
                        "risk_off": 0.45,
                        "regime": "neutral",
                        "drivers": ["balanced"],
                    },
                    summary="Fear & Greed index is 50.",
                )

        class _BusyClassifier:
            def __init__(self, *args, **kwargs):
                pass

            def classify(self, **kwargs):
                return (
                    None,
                    {
                        "provider": "ollama",
                        "requested": "phi4-mini",
                        "resolved": "",
                        "fallback_used": False,
                        "status": "error",
                        "error": "requested_model_requires_idle:override",
                        "latency_ms": 0,
                    },
                )

            def runtime(self):
                return ClassifierRuntime(
                    provider="ollama",
                    requested="phi4-mini",
                    resolved="",
                    fallback_used=False,
                    status="error",
                    error="requested_model_requires_idle:override",
                )

        config = {
            "poll": {"recommended_interval_seconds": 900, "stale_after_seconds": 2700},
            "model": {
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434",
                "requested": "phi4-mini",
                "fallbacks": [],
                "keep_alive": "0s",
            },
            "delivery": {"enabled": False},
        }

        with tempfile.TemporaryDirectory() as td:
            output_path = Path(td) / "macbook_sentiment.json"
            with mock.patch.object(producer, "_load_config", return_value=config), \
                mock.patch.object(producer, "_load_openclaw_env_vars"), \
                mock.patch.object(producer, "build_sources", return_value=[_FakeSource()]), \
                mock.patch.object(producer, "OllamaMarketClassifier", _BusyClassifier), \
                mock.patch.object(producer, "utc_now_iso", return_value="2026-03-10T12:00:00Z"), \
                mock.patch.object(producer, "emit_event"), \
                mock.patch.object(producer, "persist_raw_artifact", return_value="workspace/artifacts/market_sentiment/raw/2026/03/10/fear_greed_20260310T120000Z_deadbeef.json"), \
                mock.patch.object(producer, "persist_snapshot_artifact", return_value="workspace/artifacts/market_sentiment/normalized/2026/03/10/market_sentiment_20260310T120000Z_deadbeef.json"), \
                mock.patch.object(producer, "deliver_snapshot"):
                snapshot = producer.run_market_sentiment(output_path=output_path)
                self.assertTrue(output_path.is_file())

        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["model"]["status"], "error")
        self.assertEqual(snapshot["model"]["error"], "requested_model_requires_idle:override")
        self.assertEqual(snapshot["sources"]["fear_greed"]["status"], "degraded")
        self.assertEqual(snapshot["sources"]["fear_greed"]["classification"]["source"], "heuristic_fallback")


if __name__ == "__main__":
    unittest.main()
