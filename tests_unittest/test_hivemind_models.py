"""Tests for hivemind.models — KnowledgeUnit.to_record()."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.models import KnowledgeUnit


class TestKnowledgeUnitToRecord(unittest.TestCase):
    """Tests for KnowledgeUnit.to_record() — record serialization."""

    def _make_ku(self, kind="fact", source="test", agent_scope="coder",
                 ttl_days=None, metadata=None):
        return KnowledgeUnit(
            kind=kind,
            source=source,
            agent_scope=agent_scope,
            ttl_days=ttl_days,
            metadata=metadata or {},
        )

    def test_returns_dict(self):
        ku = self._make_ku()
        result = ku.to_record(content="text", content_hash="abc123")
        self.assertIsInstance(result, dict)

    def test_kind_field_present(self):
        ku = self._make_ku(kind="procedure")
        result = ku.to_record(content="text", content_hash="hash")
        self.assertEqual(result["kind"], "procedure")

    def test_source_field_present(self):
        ku = self._make_ku(source="codebase")
        result = ku.to_record(content="text", content_hash="hash")
        self.assertEqual(result["source"], "codebase")

    def test_agent_scope_field_present(self):
        ku = self._make_ku(agent_scope="planner")
        result = ku.to_record(content="text", content_hash="hash")
        self.assertEqual(result["agent_scope"], "planner")

    def test_content_field_present(self):
        ku = self._make_ku()
        result = ku.to_record(content="the content", content_hash="hash")
        self.assertEqual(result["content"], "the content")

    def test_content_hash_field_present(self):
        ku = self._make_ku()
        result = ku.to_record(content="text", content_hash="sha256abc")
        self.assertEqual(result["content_hash"], "sha256abc")

    def test_created_at_is_iso_string(self):
        ku = self._make_ku()
        result = ku.to_record(content="text", content_hash="hash")
        self.assertIsInstance(result["created_at"], str)
        # Should be parseable as datetime
        dt = datetime.fromisoformat(result["created_at"])
        self.assertIsNotNone(dt)

    def test_explicit_created_at_used(self):
        ku = self._make_ku()
        ts = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        result = ku.to_record(content="text", content_hash="hash", created_at=ts)
        self.assertIn("2026-03-08", result["created_at"])

    def test_no_ttl_expires_at_is_none(self):
        ku = self._make_ku(ttl_days=None)
        result = ku.to_record(content="text", content_hash="hash")
        self.assertIsNone(result["expires_at"])

    def test_ttl_days_sets_expires_at(self):
        ku = self._make_ku(ttl_days=30)
        ts = datetime(2026, 3, 8, 0, 0, 0, tzinfo=timezone.utc)
        result = ku.to_record(content="text", content_hash="hash", created_at=ts)
        expected_expiry = (ts + timedelta(days=30))
        self.assertIsNotNone(result["expires_at"])
        expiry_dt = datetime.fromisoformat(result["expires_at"])
        self.assertEqual(expiry_dt.year, expected_expiry.year)
        self.assertEqual(expiry_dt.day, expected_expiry.day)

    def test_metadata_field_present(self):
        ku = self._make_ku(metadata={"key": "value"})
        result = ku.to_record(content="text", content_hash="hash")
        self.assertEqual(result["metadata"]["key"], "value")

    def test_empty_metadata_defaults_to_empty_dict(self):
        ku = self._make_ku(metadata=None)
        result = ku.to_record(content="text", content_hash="hash")
        self.assertEqual(result["metadata"], {})

    def test_ttl_days_in_result(self):
        ku = self._make_ku(ttl_days=7)
        result = ku.to_record(content="text", content_hash="hash")
        self.assertEqual(result["ttl_days"], 7)

    def test_no_ttl_in_result(self):
        ku = self._make_ku(ttl_days=None)
        result = ku.to_record(content="text", content_hash="hash")
        self.assertIsNone(result["ttl_days"])

    def test_all_required_keys_present(self):
        ku = self._make_ku()
        result = ku.to_record(content="text", content_hash="hash")
        for key in ("kind", "source", "agent_scope", "ttl_days", "created_at",
                    "expires_at", "content_hash", "content", "metadata"):
            self.assertIn(key, result, f"Missing key: {key!r}")


class TestKnowledgeUnitInit(unittest.TestCase):
    """Tests for KnowledgeUnit initialization defaults."""

    def test_kind_stored(self):
        ku = KnowledgeUnit(kind="fact", source="s", agent_scope="coder")
        self.assertEqual(ku.kind, "fact")

    def test_ttl_days_defaults_to_none(self):
        ku = KnowledgeUnit(kind="fact", source="s", agent_scope="coder")
        self.assertIsNone(ku.ttl_days)

    def test_metadata_defaults_to_empty_dict(self):
        ku = KnowledgeUnit(kind="fact", source="s", agent_scope="coder")
        self.assertEqual(ku.metadata, {})

    def test_metadata_not_shared_between_instances(self):
        # Default factory — each instance gets its own dict
        ku1 = KnowledgeUnit(kind="a", source="s", agent_scope="c")
        ku2 = KnowledgeUnit(kind="b", source="s", agent_scope="c")
        ku1.metadata["test"] = True
        self.assertNotIn("test", ku2.metadata)


if __name__ == "__main__":
    unittest.main()
