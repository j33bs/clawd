import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import policy_router  # noqa: E402
from witness_ledger import canonicalize, commit, verify_chain  # noqa: E402


class TestWitnessLedger(unittest.TestCase):
    def _policy_path(self, root: Path) -> Path:
        payload = {
            "version": 2,
            "defaults": {"allowPaid": False, "maxTokensPerRequest": 2048, "circuitBreaker": {"failureThreshold": 3, "cooldownSec": 60, "windowSec": 60, "failOn": []}},
            "budgets": {"intents": {"coding": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000, "maxCallsPerRun": 20}}, "tiers": {"free": {"dailyTokenBudget": 100000, "dailyCallBudget": 1000}}},
            "providers": {
                "local_mock_provider": {
                    "enabled": True,
                    "paid": False,
                    "tier": "free",
                    "type": "mock",
                    "provider_id": "local_vllm",
                    "models": [{"id": "mock-model", "maxInputChars": 8000}],
                }
            },
            "routing": {"free_order": ["local_mock_provider"], "intents": {"coding": {"order": ["free"], "allowPaid": False}}},
        }
        path = root / "policy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_commit_chain_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            ts1 = "2026-02-20T00:00:00Z"
            ts2 = "2026-02-20T00:00:01Z"
            rec1 = {"intent": "coding", "provider": "local", "ok": True}
            rec2 = {"intent": "coding", "provider": "remote", "ok": False}

            first = commit(rec1, str(ledger), timestamp_utc=ts1)
            expected_first = hashlib.sha256(
                canonicalize({"seq": 1, "timestamp_utc": ts1, "prev_hash": None, "record": rec1})
            ).hexdigest()
            self.assertIsNone(first["prev_hash"])
            self.assertEqual(first["hash"], expected_first)

            second = commit(rec2, str(ledger), timestamp_utc=ts2)
            expected_second = hashlib.sha256(
                canonicalize({"seq": 2, "timestamp_utc": ts2, "prev_hash": first["hash"], "record": rec2})
            ).hexdigest()
            self.assertEqual(second["prev_hash"], first["hash"])
            self.assertEqual(second["hash"], expected_second)

            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(rows[0]["prev_hash"], None)
            self.assertEqual(rows[1]["prev_hash"], rows[0]["hash"])

    def test_tamper_detection_fails_chain_verification(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            commit({"intent": "coding", "provider": "local", "ok": True}, str(ledger), timestamp_utc="2026-02-20T00:00:00Z")
            commit({"intent": "coding", "provider": "remote", "ok": False}, str(ledger), timestamp_utc="2026-02-20T00:00:01Z")
            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            rows[0]["record"]["provider"] = "tampered-provider"
            ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            verified = verify_chain(str(ledger))
        self.assertFalse(verified["ok"])
        self.assertEqual(verified["error"], "hash_mismatch")

    def test_flag_off_produces_no_witness_ledger_writes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ledger_path = tmp / "witness_ledger.jsonl"
            with patch.dict(
                os.environ,
                {"OPENCLAW_WITNESS_LEDGER": "0", "OPENCLAW_ROUTER_PROPRIOCEPTION": "0"},
                clear=False,
            ):
                with patch.object(policy_router, "WITNESS_LEDGER_PATH", ledger_path):
                    router = policy_router.PolicyRouter(
                        policy_path=self._policy_path(tmp),
                        budget_path=tmp / "budget.json",
                        circuit_path=tmp / "circuit.json",
                        event_log=tmp / "events.jsonl",
                        handlers={"local_mock_provider": lambda payload, model_id, context: {"ok": True, "text": "ok"}},
                    )
                    out = router.execute_with_escalation("coding", {"prompt": "small patch"}, context_metadata={"agent_id": "main"})
        self.assertTrue(out["ok"])
        self.assertFalse(ledger_path.exists())


if __name__ == "__main__":
    unittest.main()
