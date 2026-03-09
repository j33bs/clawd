"""Tests for pure helpers in workspace/scripts/narrative_distill.py.

Covers:
- _norm_tokens(text) — normalised token list from text
- _jaccard_tokens(a, b) — Jaccard similarity of two texts
- _extract_entities(text) — named/mentioned entity extraction
- _extract_topics(texts, top_n) — top-n topic tokens from a corpus
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "narrative_distill.py"

_spec = _ilu.spec_from_file_location("narrative_distill_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["narrative_distill_real"] = _mod
_spec.loader.exec_module(_mod)

_norm_tokens = _mod._norm_tokens
_jaccard_tokens = _mod._jaccard_tokens
_extract_entities = _mod._extract_entities
_extract_topics = _mod._extract_topics
STOPWORDS = _mod.STOPWORDS


# ---------------------------------------------------------------------------
# _norm_tokens
# ---------------------------------------------------------------------------


class TestNormTokens(unittest.TestCase):
    """Tests for _norm_tokens() — lowercased alphanum+ token list."""

    def test_returns_list(self):
        self.assertIsInstance(_norm_tokens("hello"), list)

    def test_empty_string_returns_empty(self):
        self.assertEqual(_norm_tokens(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(_norm_tokens(None), [])

    def test_lowercases(self):
        result = _norm_tokens("Hello WORLD")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_punctuation_skipped(self):
        result = _norm_tokens("hello, world!")
        self.assertNotIn(",", result)
        self.assertNotIn("!", result)

    def test_underscores_included(self):
        # Regex includes underscore via [A-Za-z0-9_./@-]
        result = _norm_tokens("some_var")
        self.assertIn("some_var", result)

    def test_email_like_included(self):
        result = _norm_tokens("user@example.com")
        # "@" is in the charset so the whole token is kept
        self.assertTrue(any("user" in t or "@" in t for t in result))

    def test_digits_included(self):
        result = _norm_tokens("123 abc")
        self.assertIn("123", result)
        self.assertIn("abc", result)

    def test_whitespace_splits_tokens(self):
        result = _norm_tokens("one two three")
        self.assertEqual(len(result), 3)


# ---------------------------------------------------------------------------
# _jaccard_tokens
# ---------------------------------------------------------------------------


class TestJaccardTokens(unittest.TestCase):
    """Tests for _jaccard_tokens() — token Jaccard similarity in [0,1]."""

    def test_both_empty_returns_one(self):
        self.assertAlmostEqual(_jaccard_tokens("", ""), 1.0)

    def test_one_empty_returns_zero(self):
        self.assertAlmostEqual(_jaccard_tokens("", "hello"), 0.0)
        self.assertAlmostEqual(_jaccard_tokens("hello", ""), 0.0)

    def test_identical_returns_one(self):
        self.assertAlmostEqual(_jaccard_tokens("hello world", "hello world"), 1.0)

    def test_no_overlap_returns_zero(self):
        self.assertAlmostEqual(_jaccard_tokens("foo bar", "baz qux"), 0.0)

    def test_partial_overlap(self):
        # "a b" vs "a c" → inter={a}, union={a,b,c} → 1/3
        result = _jaccard_tokens("a b", "a c")
        self.assertAlmostEqual(result, 1.0 / 3.0, places=5)

    def test_symmetric(self):
        a = _jaccard_tokens("alpha beta", "beta gamma")
        b = _jaccard_tokens("beta gamma", "alpha beta")
        self.assertAlmostEqual(a, b)

    def test_result_in_zero_to_one(self):
        result = _jaccard_tokens("hello world", "world peace")
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------


class TestExtractEntities(unittest.TestCase):
    """Tests for _extract_entities() — named/mentioned entity extraction."""

    def test_returns_list(self):
        self.assertIsInstance(_extract_entities("Claude is here"), list)

    def test_empty_string_returns_empty(self):
        self.assertEqual(_extract_entities(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(_extract_entities(None), [])

    def test_at_mention_included(self):
        result = _extract_entities("@alice said hello")
        self.assertIn("@alice", result)

    def test_capitalized_word_included(self):
        result = _extract_entities("Claude is great")
        self.assertIn("Claude", result)

    def test_deduplication(self):
        result = _extract_entities("Claude Claude Claude")
        self.assertEqual(result.count("Claude"), 1)

    def test_sorted_output(self):
        result = _extract_entities("Zebra Apple Mango")
        self.assertEqual(result, sorted(result))

    def test_max_ten_results(self):
        # Create text with many distinct entities
        text = " ".join(f"Entity{i:02d}" for i in range(20))
        result = _extract_entities(text)
        self.assertLessEqual(len(result), 10)

    def test_lowercase_words_excluded(self):
        result = _extract_entities("no entities here at all")
        # Lower-case words without special chars shouldn't match
        # (unless they have dots/@ etc)
        for r in result:
            self.assertTrue(r[0].isupper() or r.startswith("@") or "." in r)


# ---------------------------------------------------------------------------
# _extract_topics
# ---------------------------------------------------------------------------


class TestExtractTopics(unittest.TestCase):
    """Tests for _extract_topics() — top-N tokens by frequency."""

    def test_returns_list(self):
        result = _extract_topics(["hello world"])
        self.assertIsInstance(result, list)

    def test_empty_corpus_returns_empty(self):
        result = _extract_topics([])
        self.assertEqual(result, [])

    def test_most_frequent_token_first(self):
        texts = ["hello hello hello", "world world", "foo"]
        result = _extract_topics(texts, top_n=3)
        self.assertEqual(result[0], "hello")

    def test_stopwords_excluded(self):
        texts = ["the quick brown fox"]
        result = _extract_topics(texts, top_n=5)
        self.assertNotIn("the", result)

    def test_short_tokens_excluded(self):
        # len <= 2 are skipped
        texts = ["go do it now"]
        result = _extract_topics(texts, top_n=5)
        for t in result:
            self.assertGreater(len(t), 2)

    def test_digit_only_tokens_excluded(self):
        texts = ["123 456 789"]
        result = _extract_topics(texts, top_n=5)
        for t in result:
            self.assertFalse(t.isdigit())

    def test_top_n_limits_results(self):
        texts = ["alpha beta gamma delta epsilon"]
        result = _extract_topics(texts, top_n=2)
        self.assertLessEqual(len(result), 2)

    def test_top_n_one_returns_one(self):
        texts = ["hello world hello"]
        result = _extract_topics(texts, top_n=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "hello")

    def test_multiple_texts_combined(self):
        texts = ["router llm", "router policy", "router test"]
        result = _extract_topics(texts, top_n=1)
        self.assertEqual(result[0], "router")


if __name__ == "__main__":
    unittest.main()
