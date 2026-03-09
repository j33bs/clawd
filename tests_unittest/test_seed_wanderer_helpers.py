"""Tests for pure helpers in workspace/scripts/seed_wanderer.py.

Covers:
- _tokenize(text, min_len=4) — lowercased keyword list with stopword filtering
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "seed_wanderer.py"

_spec = _ilu.spec_from_file_location("seed_wanderer_real", str(SCRIPT_PATH))
_mod = _ilu.module_from_spec(_spec)
sys.modules["seed_wanderer_real"] = _mod
_spec.loader.exec_module(_mod)

_tokenize = _mod._tokenize
STOPWORDS = _mod.STOPWORDS


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


class TestTokenize(unittest.TestCase):
    """Tests for _tokenize() — keyword list with min-length and stopword filter."""

    def test_returns_list(self):
        self.assertIsInstance(_tokenize("hello world"), list)

    def test_empty_string_returns_empty(self):
        self.assertEqual(_tokenize(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(_tokenize(None), [])

    def test_lowercases_input(self):
        result = _tokenize("ACTIVE INFERENCE")
        self.assertIn("active", result)
        self.assertIn("inference", result)

    def test_default_min_len_is_4(self):
        # "cat" (3 chars) should be excluded with default min_len=4
        result = _tokenize("cat elephant")
        self.assertNotIn("cat", result)
        self.assertIn("elephant", result)

    def test_custom_min_len(self):
        result = _tokenize("cat", min_len=3)
        self.assertIn("cat", result)

    def test_stopwords_excluded(self):
        # Pick a few words from STOPWORDS
        for word in sorted(STOPWORDS)[:5]:
            if len(word) >= 4:
                result = _tokenize(word)
                self.assertNotIn(word, result, f"Stopword {word!r} should be excluded")

    def test_alphanumeric_tokens_only(self):
        # Regex: [a-z][a-z0-9_]{2,} — letters/digits/underscore only
        result = _tokenize("hello-world foo.bar")
        for t in result:
            self.assertRegex(t, r"^[a-z][a-z0-9_]+$")

    def test_token_must_start_with_letter(self):
        # "123abc" starts with digit, not matched
        result = _tokenize("123abc hello")
        self.assertNotIn("123abc", result)
        self.assertIn("hello", result)

    def test_multiple_words_included(self):
        result = _tokenize("active inference model prediction")
        self.assertIn("active", result)
        self.assertIn("inference", result)

    def test_underscores_in_token(self):
        # Underscores are valid in tokens per regex [a-z][a-z0-9_]{2,}
        result = _tokenize("some_var another")
        self.assertIn("some_var", result)

    def test_token_exactly_min_len_included(self):
        # min_len=4, "abcd" is exactly 4 → included
        result = _tokenize("abcd", min_len=4)
        self.assertIn("abcd", result)

    def test_token_below_min_len_excluded(self):
        # "abc" is len 3, default min_len=4 → excluded
        result = _tokenize("abc")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
