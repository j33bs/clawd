import unittest
from unittest import mock

from workspace.market_sentiment.classifier import OllamaMarketClassifier, normalize_classification
from workspace.market_sentiment.sources import CoinGeckoSource, FearGreedSource, ForexFactorySource


class _DummyResponse:
    def __init__(self, *, status_code=200, content=b"", json_data=None):
        self.status_code = status_code
        self.content = content
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self):
        return self._json_data


class _DummySession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, *args, **kwargs):
        if not self.responses:
            raise RuntimeError("no_response")
        self.calls.append((args, kwargs))
        return self.responses.pop(0)


class TestForexFactorySource(unittest.TestCase):
    def test_parses_xml_feed(self):
        xml_text = """<?xml version="1.0" encoding="windows-1252"?>
<weeklyevents>
  <event>
    <title>CPI m/m</title>
    <country>USD</country>
    <date><![CDATA[03-10-2026]]></date>
    <time><![CDATA[8:30am]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[0.3%]]></forecast>
    <previous><![CDATA[0.2%]]></previous>
    <actual><![CDATA[0.4%]]></actual>
  </event>
</weeklyevents>
"""
        source = ForexFactorySource(name="forex_factory", config={"url": "https://example.com/feed.xml"})
        out = source.fetch(_DummySession([_DummyResponse(content=xml_text.encode("utf-8"))]))
        self.assertEqual(out.status, "ok")
        self.assertEqual(out.metrics["high_impact_next_2d"], 1)
        self.assertEqual(out.metrics["usd_high_next_2d"], 1)
        self.assertEqual(out.metrics["surprise_events_week"], 1)
        self.assertGreater(out.metrics["surprise_balance_week"], 0.0)
        self.assertTrue(out.metrics["top_surprise_events_week"])


class TestCoinGeckoSource(unittest.TestCase):
    def test_heuristic_is_positive_for_positive_breadth(self):
        source = CoinGeckoSource(name="coingecko", config={"base_url": "https://api.coingecko.com/api/v3"})
        session = _DummySession(
            [
                _DummyResponse(json_data={"data": {"market_cap_change_percentage_24h_usd": 4.0, "market_cap_percentage": {"btc": 51.2, "eth": 17.1}}}),
                _DummyResponse(json_data=[
                    {"symbol": "btc", "market_cap": 100, "price_change_percentage_24h_in_currency": 3.0, "price_change_percentage_7d_in_currency": 6.0},
                    {"symbol": "eth", "market_cap": 60, "price_change_percentage_24h_in_currency": 4.5, "price_change_percentage_7d_in_currency": 7.0},
                    {"symbol": "sol", "market_cap": 20, "price_change_percentage_24h_in_currency": 6.0, "price_change_percentage_7d_in_currency": 10.0}
                ]),
                _DummyResponse(json_data={"coins": [{"item": {"symbol": "BTC"}}, {"item": {"symbol": "ETH"}}]}),
            ]
        )
        out = source.fetch(session)
        self.assertEqual(out.status, "ok")
        self.assertGreater(out.heuristic["sentiment"], 0.0)
        self.assertEqual(out.heuristic["regime"], "risk_on")

    def test_uses_demo_api_key_header_when_present(self):
        source = CoinGeckoSource(
            name="coingecko",
            config={"base_url": "https://api.coingecko.com/api/v3", "api_key_env": "COINGECKO_API_KEY"},
        )
        session = _DummySession(
            [
                _DummyResponse(json_data={"data": {"market_cap_change_percentage_24h_usd": 0.0, "market_cap_percentage": {}}}),
                _DummyResponse(json_data=[]),
                _DummyResponse(json_data={"coins": []}),
            ]
        )
        with mock.patch.dict("os.environ", {"COINGECKO_API_KEY": "demo-key"}, clear=False):
            out = source.fetch(session)
        self.assertEqual(out.status, "ok")
        self.assertEqual(len(session.calls), 3)
        for _, kwargs in session.calls:
            self.assertEqual(kwargs["headers"]["x-cg-demo-api-key"], "demo-key")


class TestFearGreedSource(unittest.TestCase):
    def test_parses_latest_and_delta(self):
        source = FearGreedSource(name="fear_greed", config={"url": "https://api.alternative.me/fng/"})
        session = _DummySession(
            [
                _DummyResponse(
                    json_data={
                        "data": [
                            {
                                "value": "68",
                                "value_classification": "Greed",
                                "time_until_update": "12345",
                            },
                            {
                                "value": "60",
                                "value_classification": "Greed",
                            },
                        ]
                    }
                )
            ]
        )
        out = source.fetch(session)
        self.assertEqual(out.status, "ok")
        self.assertEqual(out.metrics["fear_greed_value"], 68.0)
        self.assertEqual(out.metrics["fear_greed_delta_1d"], 8.0)
        self.assertEqual(out.heuristic["regime"], "risk_on")
        self.assertGreater(out.heuristic["sentiment"], 0.0)


class TestNormalizeClassification(unittest.TestCase):
    def test_clamps_values(self):
        out = normalize_classification(
            {
                "sentiment": 2,
                "confidence": -1,
                "risk_on": 3,
                "risk_off": -2,
                "regime": "weird",
                "drivers": ["a", "b"],
            }
        )
        self.assertEqual(out["sentiment"], 1.0)
        self.assertEqual(out["confidence"], 0.0)
        self.assertEqual(out["risk_on"], 1.0)
        self.assertEqual(out["risk_off"], 0.0)
        self.assertEqual(out["regime"], "neutral")


class TestOllamaModelResolution(unittest.TestCase):
    def test_prefers_requested_base_name_when_ollama_returns_latest_tag(self):
        classifier = OllamaMarketClassifier(
            base_url="http://127.0.0.1:11434",
            requested_model="phi4-mini",
            fallback_models=["phi3:mini"],
            timeout_seconds=30,
            temperature=0.0,
            num_predict=220,
            keep_alive="0s",
        )
        with mock.patch.dict("os.environ", {"OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE": "idle"}, clear=False):
            resolved = classifier._resolve_available_model(["phi4-mini:latest", "phi3:mini"])
        self.assertEqual(resolved, "phi4-mini:latest")

    def test_runtime_does_not_mark_latest_tag_as_fallback(self):
        classifier = OllamaMarketClassifier(
            base_url="http://127.0.0.1:11434",
            requested_model="phi4-mini",
            fallback_models=["phi3:mini"],
            timeout_seconds=30,
            temperature=0.0,
            num_predict=220,
            keep_alive="0s",
        )
        classifier._resolved_model = "phi4-mini:latest"
        runtime = classifier.runtime()
        self.assertFalse(runtime.fallback_used)

    def test_classify_uses_configured_keep_alive(self):
        classifier = OllamaMarketClassifier(
            base_url="http://127.0.0.1:11434",
            requested_model="phi4-mini",
            fallback_models=["phi3:mini"],
            timeout_seconds=30,
            temperature=0.0,
            num_predict=220,
            keep_alive="0s",
        )

        with mock.patch.dict("os.environ", {"OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE": "idle"}, clear=False), \
            mock.patch("workspace.market_sentiment.classifier.requests.get", return_value=_DummyResponse(json_data={"models": [{"name": "phi4-mini:latest"}]})), \
            mock.patch("workspace.market_sentiment.classifier.requests.post", return_value=_DummyResponse(json_data={"response": "{\"sentiment\":0.1,\"confidence\":0.8,\"risk_on\":0.6,\"risk_off\":0.2,\"regime\":\"risk_on\",\"drivers\":[\"momentum\"]}", "total_duration": 15_000_000})) as post_mock:
            classification, meta = classifier.classify(
                source_name="fear_greed",
                summary="Fear & Greed is supportive.",
                metrics={"fear_greed_value": 70},
                heuristic={"sentiment": 0.2},
            )

        self.assertEqual(classification["regime"], "risk_on")
        self.assertEqual(meta["resolved"], "phi4-mini:latest")
        self.assertEqual(post_mock.call_args.kwargs["json"]["keep_alive"], "0s")

    def test_classify_skips_phi4_until_idle_and_uses_fallback(self):
        classifier = OllamaMarketClassifier(
            base_url="http://127.0.0.1:11434",
            requested_model="phi4-mini",
            fallback_models=["phi3:mini"],
            timeout_seconds=30,
            temperature=0.0,
            num_predict=220,
            keep_alive="0s",
        )

        with mock.patch.dict("os.environ", {"OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE": "busy"}, clear=False), \
            mock.patch("workspace.market_sentiment.classifier.requests.get", return_value=_DummyResponse(json_data={"models": [{"name": "phi4-mini:latest"}, {"name": "phi3:mini"}]})), \
            mock.patch("workspace.market_sentiment.classifier.requests.post", return_value=_DummyResponse(json_data={"response": "{\"sentiment\":0.1,\"confidence\":0.8,\"risk_on\":0.6,\"risk_off\":0.2,\"regime\":\"risk_on\",\"drivers\":[\"momentum\"]}", "total_duration": 15_000_000})) as post_mock:
            _, meta = classifier.classify(
                source_name="fear_greed",
                summary="Fear & Greed is supportive.",
                metrics={"fear_greed_value": 70},
                heuristic={"sentiment": 0.2},
            )

        self.assertEqual(meta["resolved"], "phi3:mini")
        self.assertTrue(meta["fallback_used"])
        self.assertEqual(post_mock.call_args.kwargs["json"]["model"], "phi3:mini")

    def test_runtime_errors_when_phi4_requires_idle_and_no_fallback_is_available(self):
        classifier = OllamaMarketClassifier(
            base_url="http://127.0.0.1:11434",
            requested_model="phi4-mini",
            fallback_models=[],
            timeout_seconds=30,
            temperature=0.0,
            num_predict=220,
            keep_alive="0s",
        )

        with mock.patch.dict("os.environ", {"OPENCLAW_MARKET_SENTIMENT_IDLE_OVERRIDE": "busy"}, clear=False), \
            mock.patch("workspace.market_sentiment.classifier.requests.get", return_value=_DummyResponse(json_data={"models": [{"name": "phi4-mini:latest"}]})):
            runtime = classifier.runtime()

        self.assertEqual(runtime.status, "error")
        self.assertEqual(runtime.resolved, "")
        self.assertIn("requested_model_requires_idle", runtime.error)


if __name__ == "__main__":
    unittest.main()
