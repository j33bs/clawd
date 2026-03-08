"""Tests for pure helpers in workspace/scripts/daily_brief_generator.py.

Uses real KB graph file for get_research_highlight().
Patches KB_GRAPH for fixture-based tests.

Covers:
- get_research_highlight() — reads KB graph, filters research: types
- generate_brief() — calls get_research_highlight, builds markdown string
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
DBG_PATH = REPO_ROOT / "workspace" / "scripts" / "daily_brief_generator.py"

_spec = _ilu.spec_from_file_location("daily_brief_generator_real", str(DBG_PATH))
dbg = _ilu.module_from_spec(_spec)
sys.modules["daily_brief_generator_real"] = dbg
_spec.loader.exec_module(dbg)


# Sample JSONL fixture: 2 research entries
RESEARCH_ENTRY_1 = {
    "name": "Test Paper Alpha",
    "entity_type": "research:memory",
    "content": "This is content for alpha.\nSecond line.",
    "metadata": {"url": "https://arxiv.org/abs/1234"},
}
RESEARCH_ENTRY_2 = {
    "name": "Test Paper Beta",
    "entity_type": "research:arousal",
    "content": "Beta content here.",
    "metadata": {"url": None},
}
NON_RESEARCH_ENTRY = {
    "name": "Some Concept",
    "entity_type": "concept:general",
    "content": "Not a research entry.",
    "metadata": {},
}


def _write_kb(tmp: str, entries: list) -> Path:
    p = Path(tmp) / "graph.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# get_research_highlight
# ---------------------------------------------------------------------------

class TestGetResearchHighlight(unittest.TestCase):
    """Tests for get_research_highlight() — reads KB, filters research: types."""

    def test_returns_dict_with_real_file(self):
        result = dbg.get_research_highlight()
        self.assertIsInstance(result, dict)

    def test_real_file_has_title(self):
        result = dbg.get_research_highlight()
        self.assertIn("title", result)

    def test_real_file_has_topic(self):
        result = dbg.get_research_highlight()
        self.assertIn("topic", result)

    def test_real_file_has_content(self):
        result = dbg.get_research_highlight()
        self.assertIn("content", result)

    def test_real_file_has_url(self):
        result = dbg.get_research_highlight()
        self.assertIn("url", result)

    def test_fixture_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY_1, RESEARCH_ENTRY_2])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        self.assertIsInstance(result, dict)

    def test_fixture_has_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY_1])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        for key in ("title", "topic", "content", "url"):
            self.assertIn(key, result)

    def test_filters_non_research_entries(self):
        """Only research: typed entries should appear."""
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [NON_RESEARCH_ENTRY])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        # No research: entries → returns None
        self.assertIsNone(result)

    def test_returns_none_when_no_research_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [{"name": "X", "entity_type": "concept", "content": "x", "metadata": {}}])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        self.assertIsNone(result)

    def test_title_truncated_to_70(self):
        long_name = "A" * 100
        entry = {"name": long_name, "entity_type": "research:test",
                 "content": "c", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        self.assertLessEqual(len(result["title"]), 70)

    def test_content_truncated_to_400(self):
        long_content = "X" * 500
        entry = {"name": "N", "entity_type": "research:test",
                 "content": long_content, "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        self.assertLessEqual(len(result["content"]), 400)

    def test_topic_is_entity_type_without_prefix(self):
        entry = {"name": "N", "entity_type": "research:memory",
                 "content": "c", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(dbg, "KB_GRAPH", kb):
                result = dbg.get_research_highlight()
        self.assertEqual(result["topic"], "memory")


# ---------------------------------------------------------------------------
# generate_brief
# ---------------------------------------------------------------------------

class TestGenerateBrief(unittest.TestCase):
    """Tests for generate_brief() — markdown string output."""

    def test_returns_string(self):
        result = dbg.generate_brief()
        self.assertIsInstance(result, str)

    def test_contains_daily_brief_header(self):
        result = dbg.generate_brief()
        self.assertIn("DAILY BRIEF", result)

    def test_contains_date(self):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        result = dbg.generate_brief()
        self.assertIn(today, result)

    def test_nonempty(self):
        result = dbg.generate_brief()
        self.assertTrue(result.strip())

    def test_is_multiline(self):
        """Brief spans multiple lines."""
        result = dbg.generate_brief()
        self.assertGreater(result.count("\n"), 3)


if __name__ == "__main__":
    unittest.main()
