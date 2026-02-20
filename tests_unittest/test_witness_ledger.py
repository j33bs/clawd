import hashlib
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from witness_ledger import canonicalize, commit  # noqa: E402


class TestWitnessLedger(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
