import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import event_envelope  # noqa: E402


class TestEventEnvelope(unittest.TestCase):
    def test_required_keys_present(self):
        env = event_envelope.make_envelope(
            event="context_guard_triggered",
            severity="warn",
            component="policy_router",
            corr_id="req-1",
            details={"estimated_tokens": 17000},
            ts="2026-02-23T01:00:00Z",
        )
        self.assertEqual(env["schema"], event_envelope.SCHEMA_ID)
        self.assertEqual(env["event"], "context_guard_triggered")
        self.assertEqual(env["severity"], "WARN")
        self.assertEqual(env["component"], "policy_router")
        self.assertEqual(env["corr_id"], "req-1")
        self.assertIsInstance(env["details"], dict)

    def test_forbidden_keys_removed(self):
        env = event_envelope.make_envelope(
            event="x",
            severity="INFO",
            component="y",
            corr_id="z",
            details={"prompt": "secret", "nested": {"text": "hidden", "ok": 1}},
            ts="2026-02-23T01:00:00Z",
        )
        self.assertFalse(event_envelope.contains_forbidden_keys(env), env)
        self.assertEqual(env["details"]["nested"]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
