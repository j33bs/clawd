"""Tests for store.sync — sections_to_records, log_collision (pure I/O functions).

lancedb, pyarrow, and sentence_transformers are mocked so no ML deps required.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Patch heavy deps before importing sync
for mod in ("lancedb", "pyarrow", "pyarrow.compute", "sentence_transformers"):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

import sync
from schema import CorrespondenceSection


def _make_section(**kwargs) -> CorrespondenceSection:
    defaults = {
        "canonical_section_number": 1,
        "section_number_filed": "I",
        "authors": [],
        "title": "",
        "body": "",
    }
    defaults.update(kwargs)
    return CorrespondenceSection(**defaults)


class TestSectionsToRecords(unittest.TestCase):
    """Tests for sections_to_records() — CorrespondenceSection → dict conversion."""

    def test_empty_list_returns_empty(self):
        result = sync.sections_to_records([])
        self.assertEqual(result, [])

    def test_returns_list(self):
        result = sync.sections_to_records([_make_section()])
        self.assertIsInstance(result, list)

    def test_single_section_single_record(self):
        result = sync.sections_to_records([_make_section()])
        self.assertEqual(len(result), 1)

    def test_two_sections_two_records(self):
        s1 = _make_section(canonical_section_number=1, section_number_filed="I")
        s2 = _make_section(canonical_section_number=2, section_number_filed="II")
        result = sync.sections_to_records([s1, s2])
        self.assertEqual(len(result), 2)

    def test_canonical_section_number_preserved(self):
        s = _make_section(canonical_section_number=42, section_number_filed="XLII")
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["canonical_section_number"], 42)

    def test_section_number_filed_preserved(self):
        s = _make_section(canonical_section_number=42, section_number_filed="XLII")
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["section_number_filed"], "XLII")

    def test_authors_preserved(self):
        s = _make_section(authors=["Claude Code", "c_lawd"])
        result = sync.sections_to_records([s])
        self.assertIn("Claude Code", result[0]["authors"])
        self.assertIn("c_lawd", result[0]["authors"])

    def test_title_preserved(self):
        s = _make_section(title="Memory routing proposal")
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["title"], "Memory routing proposal")

    def test_body_preserved(self):
        s = _make_section(body="The body text here.")
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["body"], "The body text here.")

    def test_exec_tags_preserved(self):
        s = _make_section()
        s.exec_tags = ["EXEC:MICRO"]
        result = sync.sections_to_records([s])
        self.assertIn("EXEC:MICRO", result[0]["exec_tags"])

    def test_trust_epoch_preserved(self):
        s = _make_section(trust_epoch="stable")
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["trust_epoch"], "stable")

    def test_response_to_none_becomes_empty_list(self):
        s = _make_section()
        # Default response_to is None
        self.assertIsNone(s.response_to)
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["response_to"], [])

    def test_knowledge_refs_none_becomes_empty_list(self):
        s = _make_section()
        self.assertIsNone(s.knowledge_refs)
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["knowledge_refs"], [])

    def test_response_to_list_preserved(self):
        s = _make_section()
        s.response_to = ["II", "V"]
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["response_to"], ["II", "V"])

    def test_all_required_keys_present(self):
        expected_keys = {
            "canonical_section_number", "section_number_filed", "collision",
            "authors", "created_at", "is_external_caller", "title", "body",
            "exec_tags", "status_tags", "embedding", "embedding_model_version",
            "embedding_version", "retro_dark_fields", "trust_epoch",
            "response_to", "knowledge_refs",
        }
        result = sync.sections_to_records([_make_section()])
        self.assertEqual(set(result[0].keys()), expected_keys)

    def test_collision_false_by_default(self):
        result = sync.sections_to_records([_make_section()])
        self.assertFalse(result[0]["collision"])

    def test_collision_true_preserved(self):
        s = _make_section()
        s.collision = True
        result = sync.sections_to_records([s])
        self.assertTrue(result[0]["collision"])

    def test_embedding_preserved(self):
        s = _make_section()
        s.embedding = [0.1, 0.2, 0.3]
        result = sync.sections_to_records([s])
        self.assertEqual(result[0]["embedding"], [0.1, 0.2, 0.3])

    def test_records_are_independent_dicts(self):
        s1 = _make_section(canonical_section_number=1, section_number_filed="I")
        s2 = _make_section(canonical_section_number=2, section_number_filed="II")
        result = sync.sections_to_records([s1, s2])
        self.assertIsNot(result[0], result[1])


class TestLogCollision(unittest.TestCase):
    """Tests for log_collision() — appends collision events to collision.log."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_log = sync.COLLISION_LOG
        sync.COLLISION_LOG = os.path.join(self._tmpdir.name, "collision.log")

    def tearDown(self):
        sync.COLLISION_LOG = self._original_log
        self._tmpdir.cleanup()

    def _make_collision(self, canonical=10, filed="IX", authors=None, title="Test"):
        s = _make_section(
            canonical_section_number=canonical,
            section_number_filed=filed,
            authors=authors or ["Claude Code"],
            title=title,
        )
        s.collision = True
        return s

    def test_creates_log_file(self):
        sync.log_collision(self._make_collision())
        self.assertTrue(os.path.exists(sync.COLLISION_LOG))

    def test_log_entry_is_non_empty(self):
        sync.log_collision(self._make_collision())
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertGreater(len(content), 0)

    def test_canonical_number_in_log(self):
        sync.log_collision(self._make_collision(canonical=10))
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertIn("10", content)

    def test_filed_number_in_log(self):
        sync.log_collision(self._make_collision(filed="IX"))
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertIn("IX", content)

    def test_author_in_log(self):
        sync.log_collision(self._make_collision(authors=["c_lawd"]))
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertIn("c_lawd", content)

    def test_title_in_log(self):
        sync.log_collision(self._make_collision(title="Section about governance"))
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertIn("Section about governance", content)

    def test_entry_ends_with_newline(self):
        sync.log_collision(self._make_collision())
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertTrue(content.endswith("\n"))

    def test_two_collisions_append(self):
        sync.log_collision(self._make_collision(canonical=10, filed="IX"))
        sync.log_collision(self._make_collision(canonical=20, filed="XIX"))
        content = Path(sync.COLLISION_LOG).read_text()
        self.assertIn("10", content)
        self.assertIn("20", content)

    def test_two_collisions_two_lines(self):
        sync.log_collision(self._make_collision())
        sync.log_collision(self._make_collision())
        content = Path(sync.COLLISION_LOG).read_text()
        lines = [l for l in content.splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
