"""Tests for pure helpers in workspace/scripts/kb_daily_brief.py.

Uses tempfile KB fixture and patches KB_GRAPH for isolation.

Covers:
- get_research_highlight() — reads KB, filters research: types, extracts key_points
- format_for_brief() — formats highlight into markdown lines
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
KDB_PATH = REPO_ROOT / "workspace" / "scripts" / "kb_daily_brief.py"

_spec = _ilu.spec_from_file_location("kb_daily_brief_real", str(KDB_PATH))
kdb = _ilu.module_from_spec(_spec)
sys.modules["kb_daily_brief_real"] = kdb
_spec.loader.exec_module(kdb)


def _write_kb(tmp: str, entries: list) -> Path:
    p = Path(tmp) / "graph.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


RESEARCH_ENTRY = {
    "name": "Test Research Paper",
    "entity_type": "research:memory",
    "content": "First line.\nSecond line.\nThird line.\n",
    "metadata": {"url": "https://example.com"},
}


# ---------------------------------------------------------------------------
# get_research_highlight
# ---------------------------------------------------------------------------

class TestKDBGetResearchHighlight(unittest.TestCase):
    """Tests for kb_daily_brief.get_research_highlight()."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIsInstance(result, dict)

    def test_has_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIn("title", result)

    def test_has_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIn("topic", result)

    def test_has_key_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIn("key_points", result)

    def test_has_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIn("url", result)

    def test_key_points_is_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIsInstance(result["key_points"], list)

    def test_key_points_max_three(self):
        """key_points capped at 3 lines."""
        entry = {
            "name": "N", "entity_type": "research:test",
            "content": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n",
            "metadata": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertLessEqual(len(result["key_points"]), 3)

    def test_returns_none_when_no_research(self):
        entry = {"name": "C", "entity_type": "concept:x", "content": "c", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertIsNone(result)

    def test_title_truncated_to_70(self):
        entry = {"name": "A" * 100, "entity_type": "research:t",
                 "content": "c", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertLessEqual(len(result["title"]), 70)

    def test_topic_strips_research_prefix(self):
        entry = {"name": "N", "entity_type": "research:arousal",
                 "content": "c", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.get_research_highlight()
        self.assertEqual(result["topic"], "arousal")

    def test_real_file_returns_dict(self):
        result = kdb.get_research_highlight()
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# format_for_brief
# ---------------------------------------------------------------------------

class TestFormatForBrief(unittest.TestCase):
    """Tests for format_for_brief() — markdown formatting."""

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.format_for_brief()
        self.assertIsInstance(result, str)

    def test_contains_research_highlight_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.format_for_brief()
        self.assertIn("Research Highlight", result)

    def test_returns_empty_string_when_no_entries(self):
        entry = {"name": "C", "entity_type": "concept", "content": "x", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [entry])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.format_for_brief()
        self.assertEqual(result, "")

    def test_contains_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.format_for_brief()
        self.assertIn("MEMORY", result.upper())

    def test_contains_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = _write_kb(tmp, [RESEARCH_ENTRY])
            with patch.object(kdb, "KB_GRAPH", kb):
                result = kdb.format_for_brief()
        self.assertIn("Test Research Paper", result)

    def test_real_file_returns_nonempty(self):
        result = kdb.format_for_brief()
        self.assertTrue(result.strip())


if __name__ == "__main__":
    unittest.main()
