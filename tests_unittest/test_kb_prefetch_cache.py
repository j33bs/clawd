import unittest
from pathlib import Path
from unittest.mock import patch

from workspace.knowledge_base import kb


class _FakePrefetchCache:
    def __init__(self):
        self.prefetch_rows = []
        self.hits = []

    def depth(self):
        return 2

    def record_prefetch(self, topic, docs):
        self.prefetch_rows.append((topic, list(docs)))

    def record_hit(self, hit):
        self.hits.append(bool(hit))
        return {"hit": bool(hit)}


class TestKbPrefetchCache(unittest.TestCase):
    def test_prefetch_miss_then_hit_reuses_cached_context(self):
        fake_cache = _FakePrefetchCache()
        calls = []

        def _query_topic(topic):
            calls.append(topic)
            return [f"graph:{topic}"]

        kb._PREFETCH_CONTEXT_CACHE.clear()
        with patch.object(kb, "_get_prefetch_cache", return_value=fake_cache):
            with patch.object(kb, "predict_topics", return_value=["alpha", "beta"]):
                first = kb._prefetch_with_cache("alpha beta", _query_topic, repo_root=Path("."))
                second = kb._prefetch_with_cache("alpha beta", _query_topic, repo_root=Path("."))

        self.assertGreaterEqual(len(first), 1)
        self.assertEqual(first, second)
        self.assertEqual(len(fake_cache.prefetch_rows), 1)
        self.assertEqual(fake_cache.hits, [False, True])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
