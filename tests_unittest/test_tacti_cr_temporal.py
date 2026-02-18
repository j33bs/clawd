import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.temporal import TemporalMemory  # noqa: E402


class TestTactiCRTemporal(unittest.TestCase):
    def test_retrieve_prefers_recent_relevant_entries(self):
        now = datetime(2026, 2, 18, tzinfo=timezone.utc)
        mem = TemporalMemory(retention_days=180)

        mem.store(
            "routing failure mitigation",
            importance=1.0,
            timestamp=now - timedelta(days=30),
        )
        recent = mem.store(
            "routing failure rollback",
            importance=0.6,
            timestamp=now,
        )

        results = mem.retrieve("routing failure", limit=2, now=now)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].content, recent.content)

    def test_prune_expired_respects_retention_window(self):
        now = datetime(2026, 2, 18, tzinfo=timezone.utc)
        mem = TemporalMemory(retention_days=10)
        mem.store("recent", timestamp=now - timedelta(days=2))
        mem.store("old", timestamp=now - timedelta(days=20))

        removed = mem.prune_expired(now=now)
        self.assertEqual(removed, 1)
        self.assertEqual(mem.size, 1)
        self.assertEqual(mem.retrieve("recent", limit=1, now=now)[0].content, "recent")

    def test_store_clamps_importance(self):
        now = datetime(2026, 2, 18, tzinfo=timezone.utc)
        mem = TemporalMemory()
        low = mem.store("low", importance=-2, timestamp=now)
        high = mem.store("high", importance=9, timestamp=now)
        self.assertEqual(low.importance, 0.0)
        self.assertEqual(high.importance, 1.0)

    @patch("tacti_cr.temporal.hivemind_store", return_value=True)
    def test_store_syncs_to_hivemind(self, mock_store):
        now = datetime(2026, 2, 18, tzinfo=timezone.utc)
        mem = TemporalMemory(sync_hivemind=True, agent_scope="main")
        mem.store("episode text", timestamp=now, metadata={"kind": "lesson"})
        self.assertTrue(mock_store.called)
        payload = mock_store.call_args[0][0]
        self.assertEqual(payload["source"], "tacti_cr.temporal")
        self.assertEqual(payload["kind"], "lesson")

    @patch("tacti_cr.temporal.hivemind_query")
    def test_retrieve_can_include_hivemind_context(self, mock_query):
        now = datetime(2026, 2, 18, tzinfo=timezone.utc)
        mem = TemporalMemory(sync_hivemind=False)
        mem.store("local context", timestamp=now)
        from tacti_cr.hivemind_bridge import MemoryEntry

        mock_query.return_value = [
            MemoryEntry(
                kind="fact",
                source="manual",
                agent_scope="main",
                score=7,
                created_at=now.isoformat(),
                content="hivemind context",
                metadata={},
            )
        ]
        rows = mem.retrieve("context", include_hivemind=True, limit=3, now=now)
        self.assertTrue(any(r.content == "hivemind context" for r in rows))


if __name__ == "__main__":
    unittest.main()
