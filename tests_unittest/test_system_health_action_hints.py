import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import system_health_monitor as shm  # noqa: E402


class SystemHealthActionHintsTests(unittest.TestCase):
    def test_actionable_hints_cover_coder_pairing_replay(self):
        checks = {
            "coder_vllm": {"status": "DEGRADED", "coder_degraded_reason": "VRAM_LOW"},
            "pairing_canary": {"status": "UNHEALTHY", "reason": "PAIRING_STALE"},
            "replay_log": {"status": "NOACCESS", "reason": "permission_denied"},
        }
        hints = shm.build_actionable_hints(checks)
        self.assertGreaterEqual(len(hints), 3)
        text = json.dumps(hints, sort_keys=True)
        self.assertIn("VLLM_CODER_MIN_FREE_VRAM_MB", text)
        self.assertIn("check_gateway_pairing_health.sh", text)
        self.assertIn(".local/share/openclaw/replay", text)

    def test_emit_health_event_writes_envelope(self):
        checks = {
            "coder_vllm": {"status": "DOWN", "coder_degraded_reason": "NO_BLOCK_MARKER"},
            "pairing_canary": {"status": "OK"},
            "replay_log": {"status": "WRITABLE"},
        }
        hints = shm.build_actionable_hints(checks)
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "events" / "gate_health.jsonl"
            old = os.environ.get("OPENCLAW_EVENT_ENVELOPE_LOG_PATH")
            os.environ["OPENCLAW_EVENT_ENVELOPE_LOG_PATH"] = str(log_path)
            try:
                event = shm.emit_health_event(overall_pass=True, actionable_hints=hints, checks=checks)
                self.assertEqual(event["event"], "health.degraded")
                lines = log_path.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 1)
                obj = json.loads(lines[0])
                self.assertEqual(obj["schema"], "openclaw.event_envelope.v1")
                self.assertIn("details", obj)
                self.assertNotIn("prompt", json.dumps(obj).lower())
            finally:
                if old is None:
                    os.environ.pop("OPENCLAW_EVENT_ENVELOPE_LOG_PATH", None)
                else:
                    os.environ["OPENCLAW_EVENT_ENVELOPE_LOG_PATH"] = old


if __name__ == "__main__":
    unittest.main()
