import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.itc_pipeline import ingestion_boundary as ib
from workspace.itc.api import get_itc_signal


class TestItcIngestionForwarding(unittest.TestCase):
    def test_forward_writes_queue_classifier_input_and_contract_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            queue_state = root / "telegram" / "itc_processed_messages.json"
            canon = root / "itc" / "canon" / "messages.jsonl"
            artifacts = root / "workspace" / "artifacts" / "itc"
            message = ib.IngestedMessage(
                source="telegram",
                chat_id=-100123,
                message_id=77,
                date="2026-02-22T00:00:00Z",
                sender_id=1,
                sender_name="u",
                chat_title="Into the Cryptoverse Alerts",
                text="BUY entry 10 target 12",
                raw_metadata={},
            )

            with patch.object(ib, "DEDUPE_STATE_PATH", queue_state):
                with patch.object(ib, "_ITC_CANON_PATH", canon):
                    with patch.object(ib, "_ITC_ARTIFACT_ROOT", artifacts):
                        with patch.object(ib, "_resolve_classifier", return_value=lambda text: ("trade_signal", ["trade_signal"])):
                            ib._forward_to_pipeline(message)

            queue_rows = [
                json.loads(line)
                for line in (queue_state.parent / "itc_incoming_queue.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(queue_rows), 1)
            self.assertEqual(queue_rows[0]["message_id"], 77)

            canon_rows = [json.loads(line) for line in canon.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(canon_rows), 1)
            self.assertEqual(canon_rows[0]["primary_tag"], "trade_signal")
            self.assertEqual(canon_rows[0]["all_tags"], ["trade_signal"])
            self.assertEqual(canon_rows[0]["classifier"], "ingestion_boundary.forwarder/rules")

            normalized_files = list((artifacts / "normalized").rglob("itc_signal_*.json"))
            self.assertEqual(len(normalized_files), 1)
            signal = json.loads(normalized_files[0].read_text(encoding="utf-8"))
            self.assertEqual(signal["source"], "telegram")
            self.assertEqual(signal["window"], "1h")
            self.assertEqual(signal["metrics"]["regime"], "risk_on")
            self.assertGreater(signal["metrics"]["sentiment"], 0.0)
            self.assertGreater(signal["metrics"]["confidence"], 0.0)

            selected = get_itc_signal(
                ts_utc="2026-02-22T00:15:00Z",
                lookback="8h",
                policy={"artifacts_root": str(artifacts), "run_id": "test_itc_ingestion_forwarding"},
            )
            self.assertEqual(selected["reason"], "ok")
            self.assertIsNotNone(selected["signal"])
            self.assertEqual(selected["signal"]["source"], "telegram")


if __name__ == "__main__":
    unittest.main()
