import unittest

from workspace.market_sentiment.contract import validate_snapshot


def _valid_snapshot():
    return {
        "schema_version": 1,
        "generated_at": "2026-03-10T12:00:00Z",
        "producer": "c_lawd",
        "status": "ok",
        "poll": {"recommended_interval_seconds": 900, "stale_after_seconds": 2700},
        "model": {
            "provider": "ollama",
            "requested": "phi4",
            "resolved": "phi4",
            "fallback_used": False,
            "status": "ok",
            "error": None,
        },
        "artifacts": {
            "events_ref": "workspace/artifacts/market_sentiment/events/market_sentiment_events.jsonl",
            "snapshot_ref": "workspace/artifacts/market_sentiment/normalized/2026/03/10/market_sentiment_20260310T120000Z_deadbeef.json",
        },
        "sources": {
            "coingecko": {
                "status": "ok",
                "optional": False,
                "fetched_at": "2026-03-10T12:00:00Z",
                "stale_after_seconds": 2700,
                "weight_hint": 1.25,
                "transport": {"url": "https://api.coingecko.com/api/v3", "http_status": 200},
                "raw_ref": "workspace/artifacts/market_sentiment/raw/2026/03/10/coingecko_20260310T120000Z_deadbeef.json",
                "summary": "Breadth improved.",
                "metrics": {"green_ratio_top_n": 0.6},
                "classification": {
                    "source": "phi4",
                    "sentiment": 0.3,
                    "confidence": 0.8,
                    "risk_on": 0.7,
                    "risk_off": 0.2,
                    "regime": "risk_on",
                    "drivers": ["breadth green", "market cap up"],
                    "latency_ms": 1234,
                },
            }
        },
        "aggregate": {
            "sentiment": 0.3,
            "confidence": 0.8,
            "risk_on": 0.7,
            "risk_off": 0.2,
            "regime": "risk_on",
            "sources_considered": 1,
            "source_weights": {"coingecko": 1.25},
        },
    }


class TestMarketSentimentContract(unittest.TestCase):
    def test_valid_snapshot_passes(self):
        ok, reason = validate_snapshot(_valid_snapshot())
        self.assertTrue(ok)
        self.assertTrue(reason.startswith("ok"))

    def test_missing_aggregate_fails(self):
        payload = _valid_snapshot()
        del payload["aggregate"]
        ok, reason = validate_snapshot(payload)
        self.assertFalse(ok)
        self.assertIn("aggregate", reason)

    def test_bad_sentiment_bounds_fail(self):
        payload = _valid_snapshot()
        payload["aggregate"]["sentiment"] = 2.0
        ok, reason = validate_snapshot(payload)
        self.assertFalse(ok)
        self.assertIn("aggregate.sentiment", reason)


if __name__ == "__main__":
    unittest.main()

