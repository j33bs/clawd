import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.intelligence.contradictions import detect_contradictions
from hivemind.intelligence.utils import get_all_units_cached
from hivemind.models import KnowledgeUnit
from hivemind.store import HiveMindStore


class TestIntelligenceUnitsCache(unittest.TestCase):
    def test_get_all_units_cached_hits_store_once_within_ttl(self):
        with tempfile.TemporaryDirectory() as td:
            store = HiveMindStore(Path(td) / "hivemind")
            store.put(KnowledgeUnit(kind="fact", source="x", agent_scope="shared"), "cached value")

            with patch.object(store, "all_units_cached", wraps=store.all_units_cached) as all_units_cached_mock:
                first, meta1 = get_all_units_cached(store, ttl_seconds=60)
                second, meta2 = get_all_units_cached(store, ttl_seconds=60)

            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 1)
            self.assertFalse(meta1["cache_hit"])
            self.assertTrue(meta2["cache_hit"])
            self.assertEqual(all_units_cached_mock.call_count, 1)

    def test_contradictions_accepts_units_override(self):
        sample = [
            {
                "kind": "decision",
                "content": "Use local model",
                "content_hash": "a" * 64,
                "source": "x",
                "created_at": "2026-02-21T00:00:00+00:00",
                "metadata": {"tag": "routing"},
            },
            {
                "kind": "decision",
                "content": "Do not use local model",
                "content_hash": "b" * 64,
                "source": "x",
                "created_at": "2026-02-21T01:00:00+00:00",
                "metadata": {"tag": "routing"},
            },
        ]
        reports = detect_contradictions([], units=sample)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["severity"], "critical")


if __name__ == "__main__":
    unittest.main()
