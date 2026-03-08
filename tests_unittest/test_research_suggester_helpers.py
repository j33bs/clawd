"""Tests for pure helpers in workspace/research/research_suggester.py.

Pure stdlib (random only) — no stubs needed.
Uses unittest.mock.patch to control random.random() for determinism.

Covers:
- GAPS constant structure
- INTERESTS constant
- suggest() — structure, sorting, cap at 5, random guard
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SUGGESTER_PATH = REPO_ROOT / "workspace" / "research" / "research_suggester.py"

_spec = _ilu.spec_from_file_location("research_suggester_real", str(SUGGESTER_PATH))
rs = _ilu.module_from_spec(_spec)
sys.modules["research_suggester_real"] = rs
_spec.loader.exec_module(rs)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants(unittest.TestCase):
    """Tests for GAPS and INTERESTS module-level constants."""

    def test_gaps_is_list(self):
        self.assertIsInstance(rs.GAPS, list)

    def test_gaps_nonempty(self):
        self.assertGreater(len(rs.GAPS), 0)

    def test_each_gap_is_3_tuple(self):
        for item in rs.GAPS:
            self.assertEqual(len(item), 3)

    def test_gap_name_is_string(self):
        for name, _desc, _tags in rs.GAPS:
            self.assertIsInstance(name, str)

    def test_gap_description_is_string(self):
        for _name, desc, _tags in rs.GAPS:
            self.assertIsInstance(desc, str)

    def test_gap_tags_is_string(self):
        for _name, _desc, tags in rs.GAPS:
            self.assertIsInstance(tags, str)

    def test_interests_is_list(self):
        self.assertIsInstance(rs.INTERESTS, list)

    def test_interests_nonempty(self):
        self.assertGreater(len(rs.INTERESTS), 0)

    def test_interests_strings(self):
        for item in rs.INTERESTS:
            self.assertIsInstance(item, str)


# ---------------------------------------------------------------------------
# suggest()
# ---------------------------------------------------------------------------

class TestSuggest(unittest.TestCase):
    """Tests for suggest() — always-include path and structure."""

    def test_returns_list(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        self.assertIsInstance(result, list)

    def test_max_five_results(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        self.assertLessEqual(len(result), 5)

    def test_each_item_is_dict(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIsInstance(item, dict)

    def test_each_item_has_topic(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIn("topic", item)

    def test_each_item_has_description(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIn("description", item)

    def test_each_item_has_tags(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIn("tags", item)

    def test_each_item_has_relevance(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIn("relevance", item)

    def test_relevance_is_float(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIsInstance(item["relevance"], float)

    def test_sorted_by_relevance_descending(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        relevances = [item["relevance"] for item in result]
        self.assertEqual(relevances, sorted(relevances, reverse=True))

    def test_always_random_zero_returns_empty(self):
        """random.random() <= 0.5 means condition False → no items included."""
        with patch.object(rs.random, "random", return_value=0.0):
            result = rs.suggest()
        # relevance is always 0 (no INTERESTS match tag strings character-by-character)
        # and random() = 0.0 which is not > 0.5 → nothing included
        self.assertEqual(result, [])

    def test_five_cap_when_all_include(self):
        """With 8 GAPS all included, still capped at 5."""
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        self.assertEqual(len(result), 5)

    def test_topic_names_are_strings(self):
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIsInstance(item["topic"], str)

    def test_topics_are_from_gaps(self):
        """Every suggested topic must come from the GAPS list."""
        gap_names = {g[0] for g in rs.GAPS}
        with patch.object(rs.random, "random", return_value=1.0):
            result = rs.suggest()
        for item in result:
            self.assertIn(item["topic"], gap_names)


if __name__ == "__main__":
    unittest.main()
