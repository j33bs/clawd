"""Tests for pure helpers in workspace/memory/conversation_summarizer.py.

Pure stdlib (re, pathlib, datetime, collections.Counter) — no stubs needed.
Uses tempfile for filesystem isolation.

Covers:
- ConversationSummarizer.extract_topics
- ConversationSummarizer.extract_decisions
- ConversationSummarizer.extract_questions
- ConversationSummarizer.generate_summary
"""
import importlib.util as _ilu
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARIZER_PATH = REPO_ROOT / "workspace" / "memory" / "conversation_summarizer.py"

_spec = _ilu.spec_from_file_location("conversation_summarizer_real", str(SUMMARIZER_PATH))
cs = _ilu.module_from_spec(_spec)
sys.modules["conversation_summarizer_real"] = cs
_spec.loader.exec_module(cs)


def _make_summarizer(tmp: str) -> "cs.ConversationSummarizer":
    return cs.ConversationSummarizer(memory_dir=str(tmp))


def _write_today(tmp: str, content: str) -> None:
    """Write content to today's date file in the temp memory dir."""
    today = datetime.now().strftime("%Y-%m-%d")
    p = Path(tmp) / f"{today}.md"
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# extract_topics
# ---------------------------------------------------------------------------

class TestExtractTopics(unittest.TestCase):
    """Tests for ConversationSummarizer.extract_topics() — Counter of capitalized words."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_topics()
            self.assertIsInstance(result, list)

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_topics()
            self.assertEqual(result, [])

    def test_extracts_capitalized_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "Python Python Claude Routing routing")
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_topics()
            words = [w for w, count in result]
            self.assertIn("Python", words)
            self.assertIn("Claude", words)

    def test_skips_common_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "The That This What When Where Why How From With Using Added Created Updated")
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_topics()
            words = [w for w, count in result]
            self.assertNotIn("The", words)
            self.assertNotIn("This", words)

    def test_max_20_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Write 30 unique capitalized words
            content = " ".join(f"Word{i}word" for i in range(30))
            _write_today(tmp, content)
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_topics()
            self.assertLessEqual(len(result), 20)

    def test_returns_tuples_with_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "Claude Claude Claude")
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_topics()
            if result:
                word, count = result[0]
                self.assertIsInstance(word, str)
                self.assertIsInstance(count, int)


# ---------------------------------------------------------------------------
# extract_decisions
# ---------------------------------------------------------------------------

class TestExtractDecisions(unittest.TestCase):
    """Tests for ConversationSummarizer.extract_decisions() — keyword-based filtering."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_decisions()
            self.assertIsInstance(result, list)

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_decisions()
            self.assertEqual(result, [])

    def test_extracts_decided_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "We decided to use the new routing system.\nPlain sentence.\n"
            _write_today(tmp, content)
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_decisions()
            self.assertTrue(any("decided" in r.lower() for r in result))

    def test_extracts_agreed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "The team agreed to proceed with the plan.\nPlain text here.\n")
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_decisions()
            self.assertTrue(any("agreed" in r.lower() for r in result))

    def test_excludes_short_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "decided.\n")  # too short (< 20 chars)
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_decisions()
            self.assertEqual(result, [])

    def test_excludes_long_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_line = "will " + "x" * 300  # > 200 chars
            _write_today(tmp, long_line)
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_decisions()
            self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# extract_questions
# ---------------------------------------------------------------------------

class TestExtractQuestions(unittest.TestCase):
    """Tests for ConversationSummarizer.extract_questions() — lines with '?'."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_questions()
            self.assertIsInstance(result, list)

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_questions()
            self.assertEqual(result, [])

    def test_extracts_question_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "How does the routing system work?\nPlain statement.\n")
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_questions()
            self.assertTrue(any("?" in q for q in result))

    def test_excludes_short_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_today(tmp, "Why?\n")  # < 15 chars
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_questions()
            self.assertEqual(result, [])

    def test_max_20_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Write 25 question lines
            lines = "\n".join(f"What is the purpose of module number {i}?" for i in range(25))
            _write_today(tmp, lines)
            summarizer = _make_summarizer(tmp)
            result = summarizer.extract_questions()
            self.assertLessEqual(len(result), 20)


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------

class TestGenerateSummary(unittest.TestCase):
    """Tests for ConversationSummarizer.generate_summary() — combined summary dict."""

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertIsInstance(result, dict)

    def test_has_top_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertIn("top_topics", result)

    def test_has_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertIn("decisions", result)

    def test_has_recent_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertIn("recent_questions", result)

    def test_has_topic_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertIn("topic_counts", result)

    def test_topic_counts_is_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertIsInstance(result["topic_counts"], dict)

    def test_empty_memory_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            summarizer = _make_summarizer(tmp)
            result = summarizer.generate_summary()
            self.assertEqual(result["top_topics"], [])
            self.assertEqual(result["decisions"], [])
            self.assertEqual(result["recent_questions"], [])


if __name__ == "__main__":
    unittest.main()
