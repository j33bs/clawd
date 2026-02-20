import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.models import KnowledgeUnit
from hivemind.store import HiveMindStore


class TestHiveMindStoreEfficiency(unittest.TestCase):
    def test_hash_index_load_once_and_flush_on_close(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)

            with patch.object(store, "_load_hashes", wraps=store._load_hashes) as load_mock, patch.object(
                store, "_save_hashes", wraps=store._save_hashes
            ) as save_mock:
                for i in range(10):
                    ku = KnowledgeUnit(kind="fact", source="bench", agent_scope="shared")
                    result = store.put(ku, f"tokenized content {i}")
                    self.assertTrue(result["stored"])

                self.assertEqual(load_mock.call_count, 1)
                self.assertEqual(save_mock.call_count, 0)
                store.close()
                self.assertEqual(save_mock.call_count, 1)

            hashes = json.loads(store.hash_index_path.read_text(encoding="utf-8"))
            self.assertEqual(len(hashes), 10)

    def test_search_uses_tokens_when_available_and_fallback_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)
            store.put(KnowledgeUnit(kind="fact", source="x", agent_scope="shared"), "alpha beta gamma")
            rows = store.all_units()
            self.assertIn("tokens", rows[0])
            self.assertIn("alpha", rows[0]["tokens"])

            raw_row = json.loads(store.units_path.read_text(encoding="utf-8").splitlines()[0])
            raw_row.pop("tokens", None)
            store.write_units([raw_row])

            hits = store.search(agent_scope="main", query="alpha", limit=5)
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["content_hash"], raw_row["content_hash"])

    def test_search_records_access_append_only_log(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "hivemind"
            store = HiveMindStore(base)
            store.put(KnowledgeUnit(kind="fact", source="x", agent_scope="shared"), "cache me")

            before_lines = len(store.units_path.read_text(encoding="utf-8").splitlines())
            hits = store.search(agent_scope="main", query="cache", limit=5)
            self.assertEqual(len(hits), 1)
            after_lines = len(store.units_path.read_text(encoding="utf-8").splitlines())
            self.assertEqual(before_lines, after_lines)

            access_rows = [json.loads(line) for line in store.access_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(access_rows), 1)
            self.assertEqual(access_rows[0]["content_hash"], hits[0]["content_hash"])


if __name__ == "__main__":
    unittest.main()
