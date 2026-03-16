import unittest
from unittest.mock import patch

from workspace.market_sentiment.classifier import OpenAICompatibleMarketClassifier, build_classifier


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class MarketSentimentClassifierTests(unittest.TestCase):
    def test_build_classifier_returns_openai_compatible_classifier(self):
        classifier = build_classifier(
            {
                "provider": "openai_compatible",
                "base_url": "http://127.0.0.1:8001/v1",
                "requested": "local-assistant",
            }
        )
        self.assertIsInstance(classifier, OpenAICompatibleMarketClassifier)

    def test_openai_compatible_classifier_parses_json_payload(self):
        classifier = OpenAICompatibleMarketClassifier(
            base_url="http://127.0.0.1:8001/v1",
            requested_model="local-assistant",
            fallback_models=[],
            timeout_seconds=15,
            temperature=0.0,
            num_predict=120,
            api_key="local",
        )
        with patch(
            "workspace.market_sentiment.classifier.requests.get",
            return_value=_FakeResponse({"data": [{"id": "local-assistant"}]}),
        ):
            with patch(
                "workspace.market_sentiment.classifier.requests.post",
                return_value=_FakeResponse(
                    {
                        "model": "local-assistant",
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"sentiment":0.18,"confidence":0.62,"risk_on":0.44,'
                                        '"risk_off":0.21,"regime":"neutral","drivers":["btc breadth"]}'
                                    )
                                }
                            }
                        ],
                    }
                ),
            ):
                classification, meta = classifier.classify(
                    source_name="coingecko",
                    summary="Breadth is mixed but majors are bid.",
                    metrics={"market_cap_change_24h_pct": 1.2},
                    heuristic={"sentiment": 0.1, "confidence": 0.4, "risk_on": 0.3, "risk_off": 0.1, "regime": "neutral"},
                )

        self.assertIsNotNone(classification)
        self.assertEqual(meta["provider"], "openai_compatible")
        self.assertEqual(meta["resolved"], "local-assistant")
        self.assertAlmostEqual(classification["sentiment"], 0.18, places=4)
        self.assertEqual(classification["drivers"], ["btc breadth"])


if __name__ == "__main__":
    unittest.main()
