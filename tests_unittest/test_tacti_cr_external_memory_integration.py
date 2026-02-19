import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.external_memory import append_event, healthcheck, read_events  # noqa: E402


class TestExternalMemoryIntegration(unittest.TestCase):
    def test_append_read_roundtrip_persists_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            events_path = Path(td) / "external_memory" / "events.jsonl"
            with patch.dict(os.environ, {"OPENCLAW_EXTERNAL_MEMORY_FILE": str(events_path)}):
                first_id = append_event("integration.test", {"seq": 1}, meta={"suite": "unittest"})
                second_id = append_event("integration.test", {"seq": 2}, meta={"suite": "unittest"})

                self.assertNotEqual(first_id, second_id)

                events = read_events(event_type="integration.test")
                self.assertEqual(len(events), 2)
                self.assertEqual(events[0]["payload"]["seq"], 1)
                self.assertEqual(events[1]["payload"]["seq"], 2)

                required_fields = {"event_id", "ts_utc", "event_type", "run_id", "payload", "meta"}
                for event in events:
                    self.assertTrue(required_fields.issubset(event.keys()))
                    self.assertIn("host", event["meta"])
                    self.assertIn("pid", event["meta"])

                self.assertTrue(events_path.exists())
                self.assertGreater(events_path.stat().st_size, 0)

                status = healthcheck()
                self.assertTrue(status["ok"])
                self.assertEqual(status["backend"], "jsonl")
                self.assertEqual(Path(status["path"]), events_path)
                self.assertIn("last_event_ts", status)


if __name__ == "__main__":
    unittest.main()
