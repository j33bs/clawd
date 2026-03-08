"""Tests for epistemic.py — confidence_to_label, add_with_confidence, get_knowledge_with_confidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import epistemic as ep


class TestConfidenceToLabel(unittest.TestCase):
    """Pure-function tests for confidence_to_label()."""

    def test_0_9_and_above_is_certain(self):
        self.assertEqual(ep.confidence_to_label(0.9), "certain")
        self.assertEqual(ep.confidence_to_label(1.0), "certain")

    def test_0_7_to_0_89_is_confident(self):
        self.assertEqual(ep.confidence_to_label(0.7), "confident")
        self.assertEqual(ep.confidence_to_label(0.85), "confident")

    def test_0_5_to_0_69_is_likely(self):
        self.assertEqual(ep.confidence_to_label(0.5), "likely")
        self.assertEqual(ep.confidence_to_label(0.65), "likely")

    def test_0_3_to_0_49_is_uncertain(self):
        self.assertEqual(ep.confidence_to_label(0.3), "uncertain")
        self.assertEqual(ep.confidence_to_label(0.45), "uncertain")

    def test_below_0_3_is_speculative(self):
        self.assertEqual(ep.confidence_to_label(0.0), "speculative")
        self.assertEqual(ep.confidence_to_label(0.29), "speculative")


class TestGetKnowledgeWithConfidence(unittest.TestCase):
    """Tests for get_knowledge_with_confidence()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_kb = ep.KB_FILE
        ep.KB_FILE = self._tmp / "kb" / "graph.jsonl"

    def tearDown(self):
        ep.KB_FILE = self._orig_kb
        self._tmpdir.cleanup()

    def test_returns_empty_list_when_kb_missing(self):
        # Bug fix: used to raise FileNotFoundError
        self.assertFalse(ep.KB_FILE.exists())
        result = ep.get_knowledge_with_confidence()
        self.assertEqual(result, [])

    def test_returns_empty_list_for_query_when_kb_missing(self):
        result = ep.get_knowledge_with_confidence("anything")
        self.assertEqual(result, [])

    def _write_entry(self, name: str, content: str, confidence: float = 0.7, entity_type: str = "test"):
        ep.KB_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "name": name,
            "content": content,
            "entity_type": entity_type,
            "metadata": {"confidence": confidence},
        }
        with open(ep.KB_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_returns_all_entries_without_query(self):
        self._write_entry("EntryA", "content about alpha")
        self._write_entry("EntryB", "content about beta")
        results = ep.get_knowledge_with_confidence()
        self.assertEqual(len(results), 2)

    def test_query_filters_by_content(self):
        self._write_entry("EntryA", "this is about routing")
        self._write_entry("EntryB", "this is about memory")
        results = ep.get_knowledge_with_confidence("routing")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "EntryA")

    def test_query_filters_by_name(self):
        self._write_entry("RoutingModule", "some content here")
        self._write_entry("MemoryModule", "other content here")
        results = ep.get_knowledge_with_confidence("routing")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "RoutingModule")

    def test_query_is_case_insensitive(self):
        self._write_entry("Alpha", "MEMORY routing system")
        results = ep.get_knowledge_with_confidence("memory")
        self.assertEqual(len(results), 1)

    def test_confidence_defaults_to_0_5_when_missing(self):
        ep.KB_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"name": "NoConf", "content": "content", "entity_type": "x", "metadata": {}}
        with open(ep.KB_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        results = ep.get_knowledge_with_confidence()
        self.assertEqual(results[0]["confidence"], 0.5)

    def test_content_truncated_to_200_chars(self):
        long_content = "x" * 300
        self._write_entry("Big", long_content)
        results = ep.get_knowledge_with_confidence()
        self.assertEqual(len(results[0]["content"]), 200)


class TestAddWithConfidence(unittest.TestCase):
    """Tests for add_with_confidence()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_kb = ep.KB_FILE
        ep.KB_FILE = self._tmp / "kb" / "graph.jsonl"

    def tearDown(self):
        ep.KB_FILE = self._orig_kb
        self._tmpdir.cleanup()

    def test_creates_parent_dirs(self):
        # Bug fix: used to fail if parent dirs didn't exist
        self.assertFalse(ep.KB_FILE.parent.exists())
        ep.add_with_confidence("TestName", "content here", "test_topic")
        self.assertTrue(ep.KB_FILE.parent.exists())

    def test_creates_kb_file(self):
        ep.add_with_confidence("N", "c", "t")
        self.assertTrue(ep.KB_FILE.exists())

    def test_return_value_has_required_keys(self):
        entry = ep.add_with_confidence("MyEntry", "my content", "my_topic", 0.8)
        self.assertIn("id", entry)
        self.assertIn("name", entry)
        self.assertIn("entity_type", entry)
        self.assertIn("content", entry)
        self.assertIn("source", entry)
        self.assertIn("metadata", entry)

    def test_name_field_matches_input(self):
        entry = ep.add_with_confidence("SpecificName", "content", "topic")
        self.assertEqual(entry["name"], "SpecificName")

    def test_confidence_stored_in_metadata(self):
        entry = ep.add_with_confidence("N", "c", "t", 0.85)
        self.assertEqual(entry["metadata"]["confidence"], 0.85)

    def test_confidence_label_generated(self):
        entry = ep.add_with_confidence("N", "c", "t", 0.85)
        self.assertEqual(entry["metadata"]["confidence_label"], "confident")

    def test_entity_type_prefixed_with_epistemic(self):
        entry = ep.add_with_confidence("N", "c", "routing")
        self.assertEqual(entry["entity_type"], "epistemic:routing")

    def test_source_is_epistemic(self):
        entry = ep.add_with_confidence("N", "c", "t")
        self.assertEqual(entry["source"], "epistemic")

    def test_written_entry_readable_via_get(self):
        ep.add_with_confidence("Readable", "routing system content", "test", 0.9)
        results = ep.get_knowledge_with_confidence("routing")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["confidence"], 0.9)

    def test_default_confidence_is_0_5(self):
        entry = ep.add_with_confidence("N", "c", "t")
        self.assertEqual(entry["metadata"]["confidence"], 0.5)


class TestIKnowStatement(unittest.TestCase):
    """Tests for i_know_statement() — summary output."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        self._orig_kb = ep.KB_FILE
        ep.KB_FILE = self._tmp / "kb" / "graph.jsonl"

    def tearDown(self):
        ep.KB_FILE = self._orig_kb
        self._tmpdir.cleanup()

    def test_returns_dont_know_when_kb_missing(self):
        result = ep.i_know_statement("anything")
        self.assertIn("don't have knowledge", result)

    def test_returns_knowledge_header_when_entries_exist(self):
        ep.add_with_confidence("RoutingSystem", "routing content", "routing", 0.8)
        result = ep.i_know_statement("routing")
        self.assertIn("My knowledge", result)

    def test_includes_confidence_percentage(self):
        ep.add_with_confidence("Test", "test content", "testing", 0.7)
        result = ep.i_know_statement("test")
        self.assertIn("70%", result)


if __name__ == "__main__":
    unittest.main()
