import json
import unittest
from unittest.mock import MagicMock, patch

from workspace.itc_pipeline.ingestion_boundary import IngestedMessage, _forward_to_pipeline


class TestIngestionBoundaryForwarding(unittest.TestCase):
    def test_forward_persists_when_router_returns_valid_signal(self):
        message = IngestedMessage(
            source="telegram",
            chat_id=123,
            message_id=456,
            date="2026-02-21T00:00:00Z",
            sender_id=1,
            sender_name="tester",
            chat_title="itc",
            text="classify this",
            raw_metadata={},
        )
        valid_signal = {
            "schema_version": 1,
            "source": "telegram",
            "ts_utc": "2026-02-21T00:00:00Z",
            "window": "8h",
            "metrics": {
                "risk_on": 0.4,
                "risk_off": 0.6,
                "sentiment": 0.2,
                "regime": "neutral",
                "confidence": 0.8,
            },
            "raw_ref": "pending://raw_ref",
            "signature": "sha256:" + "a" * 64,
        }

        router = MagicMock()
        router.execute_with_escalation.return_value = {"ok": True, "text": json.dumps(valid_signal)}

        with patch("workspace.itc_pipeline.ingestion_boundary.PolicyRouter", return_value=router), patch(
            "workspace.itc_pipeline.ingestion_boundary.persist_artifacts"
        ) as persist_mock:
            _forward_to_pipeline(message)

        persist_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
