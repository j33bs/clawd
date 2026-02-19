import json
import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.ingest.handoffs import ingest_handoffs, parse_frontmatter
from hivemind.store import HiveMindStore


class TestIngestHandoffs(unittest.TestCase):
    def test_frontmatter_parse_and_ttl_handling(self):
        handoff_text = """---
Status: Open
From: codex
Date: 2026-02-17
---

handoff body
"""
        meta = parse_frontmatter(handoff_text)
        self.assertEqual(meta["status"], "Open")
        self.assertEqual(meta["from"], "codex")

        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)
            handoffs_dir = Path(td) / "handoffs"
            handoffs_dir.mkdir(parents=True, exist_ok=True)
            (handoffs_dir / "x.md").write_text(handoff_text, encoding="utf-8")

            res = ingest_handoffs(handoffs_dir=handoffs_dir, store=store)
            self.assertEqual(res["processed"], 1)
            units = store.all_units()
            self.assertEqual(len(units), 1)
            self.assertEqual(units[0]["kind"], "handoff")
            self.assertIsNotNone(units[0]["expires_at"])

            # Force expiry and assert query omits the expired entry.
            units[0]["expires_at"] = "2000-01-01T00:00:00+00:00"
            store.units_path.write_text(json.dumps(units[0]) + "\n", encoding="utf-8")
            hits = store.search(agent_scope="main", query="handoff", limit=5)
            self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
