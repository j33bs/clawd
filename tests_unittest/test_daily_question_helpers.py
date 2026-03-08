"""Tests for pure helpers in workspace/exam_prep/daily_question.py.

Pure stdlib (os, datetime) — uses real questions.md (15 questions) plus a
temp fixture for isolation.  Patches QUESTIONS_FILE to control content.

Covers:
- load_questions
- get_daily_question
- get_answer
"""
import importlib.util as _ilu
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_Q_PATH = REPO_ROOT / "workspace" / "exam_prep" / "daily_question.py"

_spec = _ilu.spec_from_file_location("daily_question_real", str(DAILY_Q_PATH))
dq = _ilu.module_from_spec(_spec)
sys.modules["daily_question_real"] = dq
_spec.loader.exec_module(dq)


# ---------------------------------------------------------------------------
# Sample fixture — 3 questions with proper format
# ---------------------------------------------------------------------------

SAMPLE_CONTENT = (
    "# Practice Questions\n"
    "\n## Question 1 (Cat A)\n"
    "What is 2+2?\n\n"
    "A) 3\nB) 4\nC) 5\n\n"
    "**Answer:** B - It is four.\n\n---\n"
    "\n## Question 2 (Cat B)\n"
    "What is 3+3?\n\n"
    "A) 5\nB) 6\nC) 7\n\n"
    "**Answer:** B - It is six.\n\n---\n"
    "\n## Question 3 (Cat C)\n"
    "What is 4+4?\n\n"
    "A) 7\nB) 8\nC) 9\n\n"
    "**Answer:** B - It is eight.\n\n---\n"
)


def _write_sample(tmp: str) -> str:
    p = Path(tmp) / "questions.md"
    p.write_text(SAMPLE_CONTENT, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# load_questions
# ---------------------------------------------------------------------------

class TestLoadQuestions(unittest.TestCase):
    """Tests for load_questions() — parses markdown into list of question blobs."""

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.load_questions()
        self.assertIsInstance(result, list)

    def test_correct_count_from_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.load_questions()
        self.assertEqual(len(result), 3)

    def test_each_item_is_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.load_questions()
        for item in result:
            self.assertIsInstance(item, str)

    def test_items_contain_answer_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.load_questions()
        for item in result:
            self.assertIn("**Answer:**", item)

    def test_real_file_returns_list(self):
        """load_questions works against the real questions.md."""
        result = dq.load_questions()
        self.assertIsInstance(result, list)

    def test_real_file_count_15(self):
        result = dq.load_questions()
        self.assertEqual(len(result), 15)

    def test_real_file_items_nonempty(self):
        result = dq.load_questions()
        for item in result:
            self.assertTrue(item.strip())


# ---------------------------------------------------------------------------
# get_daily_question
# ---------------------------------------------------------------------------

class TestGetDailyQuestion(unittest.TestCase):
    """Tests for get_daily_question() — formatted question for today's date."""

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.get_daily_question()
        self.assertIsInstance(result, str)

    def test_starts_with_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.get_daily_question()
        self.assertTrue(result.startswith("##"))

    def test_does_not_contain_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.get_daily_question()
        self.assertNotIn("**Answer:**", result)

    def test_real_file_returns_nonempty(self):
        result = dq.get_daily_question()
        self.assertTrue(result.strip())

    def test_real_file_starts_with_heading(self):
        result = dq.get_daily_question()
        self.assertTrue(result.startswith("##"))

    def test_real_file_no_answer_marker(self):
        result = dq.get_daily_question()
        self.assertNotIn("**Answer:**", result)

    def test_single_question_file_always_returns_it(self):
        """With 1 question, day_of_year % 1 == 0 always — always returns that q."""
        single = (
            "# Questions\n"
            "\n## Question 1 (Only)\n"
            "Is this the only one?\n\n"
            "**Answer:** Yes.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "q.md"
            p.write_text(single, encoding="utf-8")
            with patch.object(dq, "QUESTIONS_FILE", str(p)):
                result = dq.get_daily_question()
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# get_answer
# ---------------------------------------------------------------------------

class TestGetAnswer(unittest.TestCase):
    """Tests for get_answer() — answer text for today's question."""

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.get_answer()
        self.assertIsInstance(result, str)

    def test_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.get_answer()
        self.assertTrue(result.strip())

    def test_does_not_start_with_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            qfile = _write_sample(tmp)
            with patch.object(dq, "QUESTIONS_FILE", qfile):
                result = dq.get_answer()
        self.assertFalse(result.startswith("##"))

    def test_real_file_nonempty(self):
        result = dq.get_answer()
        self.assertTrue(result.strip())

    def test_real_file_is_string(self):
        result = dq.get_answer()
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
