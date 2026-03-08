"""Tests for workspace/knowledge_base/agentic/synthesize.py pure helper functions.

Covers (no I/O, no network):
- build_answer
- summarize_content
- combine_contents
- calculate_confidence
- format_citations
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNTH_DIR = REPO_ROOT / "workspace" / "knowledge_base" / "agentic"
if str(SYNTH_DIR) not in sys.path:
    sys.path.insert(0, str(SYNTH_DIR))

from synthesize import (  # noqa: E402
    build_answer,
    calculate_confidence,
    combine_contents,
    format_citations,
    summarize_content,
)


# ---------------------------------------------------------------------------
# build_answer
# ---------------------------------------------------------------------------

class TestBuildAnswer(unittest.TestCase):
    """Tests for build_answer() — routes to summarize/combine based on query."""

    def test_empty_contents_returns_no_info(self):
        result = build_answer("what?", [], {})
        self.assertIn("No relevant", result)

    def test_decision_query_matched(self):
        contents = ["we decided to use Redis for caching data"]
        result = build_answer("what did we decide?", contents, {})
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_how_query_returns_summary(self):
        result = build_answer("how does it work?", ["explains the mechanism clearly"], {})
        self.assertIsInstance(result, str)

    def test_returns_string(self):
        self.assertIsInstance(build_answer("question", ["content"], {}), str)

    def test_multiple_contents_combined(self):
        contents = ["part one info", "part two info", "part three info"]
        result = build_answer("general query", contents, {})
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# summarize_content
# ---------------------------------------------------------------------------

class TestSummarizeContent(unittest.TestCase):
    """Tests for summarize_content() — trims long content at sentence boundary."""

    def test_short_content_returned_as_is(self):
        result = summarize_content("Short text.")
        self.assertIn("Short text", result)

    def test_long_content_truncated(self):
        long = "x" * 400
        result = summarize_content(long)
        self.assertLess(len(result), 400)

    def test_appends_ellipsis_when_truncated(self):
        long = "a " * 200  # 400 chars
        result = summarize_content(long)
        self.assertIn("...", result)

    def test_returns_string(self):
        self.assertIsInstance(summarize_content("text"), str)

    def test_mode_parameter_accepted(self):
        result = summarize_content("content here", mode="decision")
        self.assertIsInstance(result, str)

    def test_sentence_boundary_respected(self):
        content = "Sentence one. Sentence two. " + "filler " * 50
        result = summarize_content(content)
        # Should end before 300 chars, ideally at sentence boundary
        self.assertLessEqual(len(result), 310)


# ---------------------------------------------------------------------------
# combine_contents
# ---------------------------------------------------------------------------

class TestCombineContents(unittest.TestCase):
    """Tests for combine_contents() — merges multiple content snippets."""

    def test_empty_returns_no_info(self):
        result = combine_contents([])
        self.assertIn("No information", result)

    def test_single_item_summarized(self):
        result = combine_contents(["only one item here"])
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_multiple_items_joined(self):
        result = combine_contents(["alpha text", "beta text", "gamma text"])
        self.assertIsInstance(result, str)

    def test_result_within_length_limit(self):
        contents = ["content " * 20 for _ in range(5)]
        result = combine_contents(contents)
        self.assertLessEqual(len(result), 450)  # 400 + "..." + separator

    def test_returns_string(self):
        self.assertIsInstance(combine_contents(["a", "b"]), str)


# ---------------------------------------------------------------------------
# calculate_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence(unittest.TestCase):
    """Tests for calculate_confidence() — scores 0–1 based on content + intent."""

    def test_empty_contents_returns_0(self):
        self.assertAlmostEqual(calculate_confidence([], {}), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(calculate_confidence(["text"], {}), float)

    def test_result_in_unit_interval(self):
        val = calculate_confidence(["x" * 200, "y" * 200], {"confidence": 0.9})
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_more_contents_higher_confidence(self):
        low = calculate_confidence(["a"], {})
        high = calculate_confidence(["a" * 200, "b" * 200, "c" * 200], {})
        self.assertGreater(high, low)

    def test_short_content_penalized(self):
        long_val = calculate_confidence(["x" * 200], {})
        short_val = calculate_confidence(["abc"], {})  # avg_length < 50
        self.assertGreaterEqual(long_val, short_val)

    def test_intent_confidence_factored_in(self):
        low_intent = calculate_confidence(["text"], {"confidence": 0.1})
        high_intent = calculate_confidence(["text"], {"confidence": 0.9})
        self.assertGreater(high_intent, low_intent)


# ---------------------------------------------------------------------------
# format_citations
# ---------------------------------------------------------------------------

class TestFormatCitations(unittest.TestCase):
    """Tests for format_citations() — markdown bullet list or empty string."""

    def test_empty_citations_returns_empty_string(self):
        result = format_citations([])
        self.assertEqual(result, "")

    def test_single_citation_formatted(self):
        result = format_citations(["KB: doc1.md"])
        self.assertIn("KB: doc1.md", result)
        self.assertIn("**Sources:**", result)

    def test_multiple_citations_all_listed(self):
        result = format_citations(["src1", "src2", "src3"])
        self.assertIn("src1", result)
        self.assertIn("src2", result)
        self.assertIn("src3", result)

    def test_returns_string(self):
        self.assertIsInstance(format_citations(["x"]), str)

    def test_bullet_format(self):
        result = format_citations(["item"])
        self.assertIn("- item", result)


if __name__ == "__main__":
    unittest.main()
