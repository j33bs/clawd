"""Tests for workspace/research/insight_tracker.py pure helpers.

Covers (no network, tempfile only):
- InsightTracker.add_insight
- InsightTracker.get_by_tag
- InsightTracker.search
- InsightTracker.add_connection / get_all
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = REPO_ROOT / "workspace" / "research"
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

from insight_tracker import InsightTracker  # noqa: E402


def _tracker(td: str) -> InsightTracker:
    """Build an InsightTracker backed by a temp path."""
    path = Path(td) / "insights.json"
    return InsightTracker(path=str(path))


# ---------------------------------------------------------------------------
# add_insight
# ---------------------------------------------------------------------------

class TestAddInsight(unittest.TestCase):
    """Tests for InsightTracker.add_insight()."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            result = t.add_insight("test insight", "general")
            self.assertIsInstance(result, dict)

    def test_text_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            result = t.add_insight("hello world", "general")
            self.assertEqual(result["text"], "hello world")

    def test_category_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            result = t.add_insight("text", "architecture")
            self.assertEqual(result["category"], "architecture")

    def test_tags_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            result = t.add_insight("text", tags=["AI", "memory"])
            self.assertIn("AI", result["tags"])
            self.assertIn("memory", result["tags"])

    def test_id_increments(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            r1 = t.add_insight("first")
            r2 = t.add_insight("second")
            self.assertNotEqual(r1["id"], r2["id"])

    def test_persisted_to_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "insights.json"
            t = InsightTracker(path=str(path))
            t.add_insight("persisted insight", "test")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["insights"]), 1)


# ---------------------------------------------------------------------------
# get_by_tag
# ---------------------------------------------------------------------------

class TestGetByTag(unittest.TestCase):
    """Tests for InsightTracker.get_by_tag()."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            self.assertIsInstance(t.get_by_tag("nonexistent"), list)

    def test_empty_when_no_tag(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("no tags here", "general")
            self.assertEqual(t.get_by_tag("missing"), [])

    def test_finds_by_tag(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("tagged insight", tags=["memory"])
            t.add_insight("untagged insight", tags=[])
            result = t.get_by_tag("memory")
            self.assertEqual(len(result), 1)
            self.assertIn("tagged insight", result[0]["text"])

    def test_multiple_tags(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("a", tags=["alpha"])
            t.add_insight("b", tags=["alpha"])
            t.add_insight("c", tags=["beta"])
            result = t.get_by_tag("alpha")
            self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch(unittest.TestCase):
    """Tests for InsightTracker.search()."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            self.assertIsInstance(t.search("anything"), list)

    def test_empty_when_no_match(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("hello world", "general")
            self.assertEqual(t.search("zzz"), [])

    def test_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("Transformer attention", "implementation")
            result = t.search("transformer")
            self.assertEqual(len(result), 1)

    def test_partial_match(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("memory consolidation during sleep", "research")
            result = t.search("consolid")
            self.assertEqual(len(result), 1)

    def test_multiple_results(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("memory A", "research")
            t.add_insight("memory B", "research")
            t.add_insight("unrelated")
            result = t.search("memory")
            self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# get_all / add_connection
# ---------------------------------------------------------------------------

class TestGetAll(unittest.TestCase):
    """Tests for InsightTracker.get_all() and add_connection()."""

    def test_empty_initially(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            self.assertEqual(t.get_all(), [])

    def test_get_all_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            self.assertIsInstance(t.get_all(), list)

    def test_add_and_get_all(self):
        with tempfile.TemporaryDirectory() as td:
            t = _tracker(td)
            t.add_insight("insight1")
            t.add_insight("insight2")
            self.assertEqual(len(t.get_all()), 2)

    def test_add_connection_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "insights.json"
            t = InsightTracker(path=str(path))
            r1 = t.add_insight("from insight")
            r2 = t.add_insight("to insight")
            t.add_connection(r1["id"], r2["id"], "leads_to")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["connections"]), 1)
            self.assertEqual(data["connections"][0]["relationship"], "leads_to")


if __name__ == "__main__":
    unittest.main()
