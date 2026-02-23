import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import pairing_preflight  # noqa: E402


class PairingPreflightTests(unittest.TestCase):
    def setUp(self):
        pairing_preflight._reset_for_tests()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "state.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_guard_missing_maps_to_pairing_missing(self):
        result = pairing_preflight.ensure_pairing_healthy(
            corr_id="t_missing",
            guard_path=Path(self.tmpdir.name) / "missing_guard.sh",
            state_path=self.state_path,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], pairing_preflight.PAIRING_MISSING)
        self.assertIn("remedy", result)

    def test_remote_required_maps_reason(self):
        result = pairing_preflight.ensure_pairing_healthy(
            corr_id="t_remote",
            guard_path=__file__,
            run_guard=lambda: (3, "", "pairing required"),
            state_path=self.state_path,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], pairing_preflight.PAIRING_REMOTE_REQUIRED)

    def test_stale_then_repair_then_ok(self):
        calls = {"count": 0}

        def guard_runner():
            calls["count"] += 1
            if calls["count"] == 1:
                return (2, "pending pairing", "")
            return (0, "ok", "")

        result = pairing_preflight.ensure_pairing_healthy(
            corr_id="t_stale_ok",
            guard_path=__file__,
            run_guard=guard_runner,
            run_repair=lambda: (0, '{"ok":true}', ""),
            state_path=self.state_path,
            cooldown_seconds=0,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], pairing_preflight.PAIRING_STALE)
        self.assertTrue(result.get("safe_to_retry_now"))
        self.assertTrue(result.get("repair_attempted"))

    def test_cooldown_prevents_tight_repair_loop(self):
        guard_runner = lambda: (2, "pending pairing", "")
        repair_runner = lambda: (1, "", "failed")
        first = pairing_preflight.ensure_pairing_healthy(
            corr_id="t_cooldown_1",
            guard_path=__file__,
            run_guard=guard_runner,
            run_repair=repair_runner,
            state_path=self.state_path,
            cooldown_seconds=60,
        )
        second = pairing_preflight.ensure_pairing_healthy(
            corr_id="t_cooldown_2",
            guard_path=__file__,
            run_guard=guard_runner,
            run_repair=repair_runner,
            state_path=self.state_path,
            cooldown_seconds=60,
        )
        self.assertFalse(first["ok"])
        self.assertEqual(first["reason"], pairing_preflight.PAIRING_REMEDIATION_FAILED)
        self.assertFalse(second["ok"])
        self.assertEqual(second["reason"], pairing_preflight.PAIRING_LOCKED)


if __name__ == "__main__":
    unittest.main()
