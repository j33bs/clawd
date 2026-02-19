import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence import pruning
from hivemind.store import HiveMindStore


class TestPruning(unittest.TestCase):
    def test_ttl_expiry_and_safety_guards(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)

            now = datetime.now(timezone.utc)
            old = (now - timedelta(days=120)).isoformat()
            expired = (now - timedelta(days=1)).isoformat()

            rows = [
                {
                    "kind": "fact",
                    "source": "x",
                    "agent_scope": "shared",
                    "created_at": old,
                    "expires_at": expired,
                    "content_hash": "a",
                    "content": "ttl item",
                    "metadata": {},
                    "access_count": 0,
                },
                {
                    "kind": "decision",
                    "source": "x",
                    "agent_scope": "shared",
                    "created_at": old,
                    "expires_at": None,
                    "content_hash": "b",
                    "content": "important decision",
                    "metadata": {"confidence": 0.1},
                    "access_count": 0,
                },
            ]
            store.write_units(rows)

            pruning.REPO_ROOT = Path(td)
            pruning.ARCHIVE_DIR = base / "archive"
            pruning.REVIEW_QUEUE = base / "review_queue.json"
            pruning.PRUNE_LOG = base / "prune.log"

            report = pruning.prune_expired_and_stale(dry_run=False, store=store)
            self.assertGreaterEqual(report["archived"], 1)
            self.assertTrue((base / "archive").exists())
            self.assertTrue((base / "prune.log").exists())
            self.assertTrue((base / "review_queue.json").exists())

            kept = store.all_units()
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["kind"], "decision")


if __name__ == "__main__":
    unittest.main()
