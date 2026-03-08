"""Tests for workspace/knowledge_base/chunking.py pure helper functions.

Covers (no MLX, no embedder instantiation):
- tokenize_approx
- count_tokens
- _markdown_sections
- _token_windows
- _chunk_section_text
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "workspace" / "knowledge_base"

# Stub out the heavy embeddings driver before importing chunking.py
sys.modules.setdefault("embeddings", MagicMock())
sys.modules.setdefault("embeddings.driver_mlx", MagicMock())
_driver_mock = sys.modules["embeddings.driver_mlx"]
_driver_mock.CANONICAL_MODEL_ID = "model-a"
_driver_mock.ACCEL_MODEL_ID = "model-b"

if str(KB_DIR) not in sys.path:
    sys.path.insert(0, str(KB_DIR))

from chunking import (  # noqa: E402
    _chunk_section_text,
    _markdown_sections,
    _token_windows,
    count_tokens,
    tokenize_approx,
)


# ---------------------------------------------------------------------------
# tokenize_approx
# ---------------------------------------------------------------------------

class TestTokenizeApprox(unittest.TestCase):
    """Tests for tokenize_approx() — word+punctuation tokenizer."""

    def test_simple_words(self):
        result = tokenize_approx("hello world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_punctuation_kept_as_tokens(self):
        result = tokenize_approx("hello!")
        self.assertIn("!", result)

    def test_numbers_kept(self):
        result = tokenize_approx("value 42")
        self.assertIn("42", result)

    def test_empty_string_returns_empty(self):
        self.assertEqual(tokenize_approx(""), [])

    def test_none_safe(self):
        result = tokenize_approx(None)
        self.assertIsInstance(result, list)

    def test_returns_list(self):
        self.assertIsInstance(tokenize_approx("abc"), list)


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------

class TestCountTokens(unittest.TestCase):
    """Tests for count_tokens() — token count from text."""

    def test_basic_count(self):
        self.assertEqual(count_tokens("hello world"), 2)

    def test_empty_is_zero(self):
        self.assertEqual(count_tokens(""), 0)

    def test_punctuation_counted(self):
        count = count_tokens("hello, world!")
        self.assertEqual(count, 4)  # "hello", ",", "world", "!"

    def test_returns_int(self):
        self.assertIsInstance(count_tokens("text"), int)


# ---------------------------------------------------------------------------
# _markdown_sections
# ---------------------------------------------------------------------------

class TestMarkdownSections(unittest.TestCase):
    """Tests for _markdown_sections() — splits text into (heading, body) pairs."""

    def test_single_heading(self):
        result = _markdown_sections("# Title\nbody text")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "Title")
        self.assertEqual(result[0][1], "body text")

    def test_two_headings(self):
        result = _markdown_sections("# H1\nbody1\n## H2\nbody2")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "H1")
        self.assertEqual(result[1][0], "H2")

    def test_no_heading_returns_empty_heading(self):
        result = _markdown_sections("no heading here")
        self.assertEqual(result[0][0], "")
        self.assertIn("no heading", result[0][1])

    def test_empty_string_still_returns_list(self):
        result = _markdown_sections("")
        self.assertIsInstance(result, list)

    def test_heading_body_stripped(self):
        result = _markdown_sections("# Title\n\nbody with spaces\n")
        self.assertEqual(result[0][0], "Title")

    def test_returns_list_of_tuples(self):
        result = _markdown_sections("# H\nbody")
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], tuple)


# ---------------------------------------------------------------------------
# _token_windows
# ---------------------------------------------------------------------------

class TestTokenWindows(unittest.TestCase):
    """Tests for _token_windows() — sliding window over tokens."""

    def test_no_overlap_contiguous(self):
        tokens = ["a", "b", "c", "d"]
        windows = list(_token_windows(tokens, max_tokens=2, overlap_tokens=0))
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0], ["a", "b"])
        self.assertEqual(windows[1], ["c", "d"])

    def test_overlap_creates_more_windows(self):
        tokens = ["a", "b", "c", "d"]
        windows = list(_token_windows(tokens, max_tokens=2, overlap_tokens=1))
        self.assertGreater(len(windows), 2)

    def test_empty_tokens_returns_empty(self):
        result = list(_token_windows([], max_tokens=10, overlap_tokens=2))
        self.assertEqual(result, [])

    def test_single_window_when_tokens_fit(self):
        tokens = ["x", "y"]
        windows = list(_token_windows(tokens, max_tokens=100, overlap_tokens=10))
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0], ["x", "y"])

    def test_returns_lists(self):
        result = list(_token_windows(["a", "b", "c"], max_tokens=2, overlap_tokens=1))
        for w in result:
            self.assertIsInstance(w, list)


# ---------------------------------------------------------------------------
# _chunk_section_text
# ---------------------------------------------------------------------------

class TestChunkSectionText(unittest.TestCase):
    """Tests for _chunk_section_text() — paragraph-aware chunking."""

    def test_short_text_one_chunk(self):
        result = _chunk_section_text("short text here", max_tokens=100, overlap_tokens=5)
        self.assertEqual(len(result), 1)

    def test_two_paragraphs_fit_in_one_chunk(self):
        text = "para one\n\npara two"
        result = _chunk_section_text(text, max_tokens=100, overlap_tokens=5)
        self.assertEqual(len(result), 1)

    def test_empty_text_returns_empty(self):
        result = _chunk_section_text("", max_tokens=100, overlap_tokens=5)
        self.assertEqual(result, [])

    def test_returns_list_of_strings(self):
        result = _chunk_section_text("hello world", max_tokens=100, overlap_tokens=5)
        for chunk in result:
            self.assertIsInstance(chunk, str)

    def test_large_paragraph_splits(self):
        # A single para that exceeds max_tokens forces windowing
        big = " ".join(["word"] * 200)
        result = _chunk_section_text(big, max_tokens=50, overlap_tokens=5)
        self.assertGreater(len(result), 1)


if __name__ == "__main__":
    unittest.main()
