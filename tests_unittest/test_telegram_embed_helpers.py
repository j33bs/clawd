"""Tests for pure helpers in workspace/scripts/telegram_embed.py.

All stdlib — no network calls, no ML model downloads.
Focuses on deterministic, testable helpers only.

Covers:
- l2_normalize
- cosine_similarity
- DeterministicHashEmbedder.embed
- KeywordStubEmbedder._tokenize
- KeywordStubEmbedder.embed
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

_spec = _ilu.spec_from_file_location(
    "telegram_embed_real",
    str(SCRIPTS_DIR / "telegram_embed.py"),
)
te = _ilu.module_from_spec(_spec)
sys.modules["telegram_embed_real"] = te
_spec.loader.exec_module(te)


# ---------------------------------------------------------------------------
# l2_normalize
# ---------------------------------------------------------------------------

class TestL2Normalize(unittest.TestCase):
    """Tests for l2_normalize() — L2 unit normalization."""

    def test_unit_vector_unchanged(self):
        result = te.l2_normalize([1.0, 0.0, 0.0])
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(result[1], 0.0)

    def test_zero_vector_returns_zeros(self):
        result = te.l2_normalize([0.0, 0.0, 0.0])
        self.assertEqual(result, [0.0, 0.0, 0.0])

    def test_result_has_unit_norm(self):
        import math
        result = te.l2_normalize([3.0, 4.0])
        norm = math.sqrt(sum(v * v for v in result))
        self.assertAlmostEqual(norm, 1.0)

    def test_negative_elements_preserved(self):
        result = te.l2_normalize([-1.0, 0.0])
        self.assertAlmostEqual(result[0], -1.0)
        self.assertAlmostEqual(result[1], 0.0)

    def test_returns_list(self):
        result = te.l2_normalize([1.0, 2.0])
        self.assertIsInstance(result, list)

    def test_length_preserved(self):
        v = [1.0, 2.0, 3.0]
        self.assertEqual(len(te.l2_normalize(v)), len(v))


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity(unittest.TestCase):
    """Tests for cosine_similarity() — cosine between two vectors."""

    def test_identical_vectors_one(self):
        v = [1.0, 2.0, 3.0]
        result = te.cosine_similarity(v, v)
        self.assertAlmostEqual(result, 1.0)

    def test_zero_vectors_zero(self):
        result = te.cosine_similarity([0.0, 0.0], [0.0, 0.0])
        self.assertAlmostEqual(result, 0.0)

    def test_dimension_mismatch_raises(self):
        with self.assertRaises(ValueError):
            te.cosine_similarity([1.0, 2.0], [1.0])

    def test_bounded_result(self):
        result = te.cosine_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertGreaterEqual(result, -1.0)
        self.assertLessEqual(result, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(te.cosine_similarity([1.0], [1.0]), float)


# ---------------------------------------------------------------------------
# DeterministicHashEmbedder.embed
# ---------------------------------------------------------------------------

class TestDeterministicHashEmbedder(unittest.TestCase):
    """Tests for DeterministicHashEmbedder — deterministic SHA-256 embeddings."""

    def setUp(self):
        self.embedder = te.DeterministicHashEmbedder(dim=8)

    def test_returns_list(self):
        result = self.embedder.embed(["hello"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_correct_dim(self):
        result = self.embedder.embed(["hello world"])
        self.assertEqual(len(result[0]), 8)

    def test_deterministic(self):
        a = self.embedder.embed(["active inference"])
        b = self.embedder.embed(["active inference"])
        self.assertEqual(a, b)

    def test_different_texts_usually_differ(self):
        a = self.embedder.embed(["apple"])
        b = self.embedder.embed(["banana"])
        self.assertNotEqual(a, b)

    def test_empty_text(self):
        result = self.embedder.embed([""])
        self.assertEqual(len(result[0]), 8)

    def test_multiple_texts(self):
        result = self.embedder.embed(["foo", "bar", "baz"])
        self.assertEqual(len(result), 3)

    def test_output_is_unit_normalized(self):
        import math
        result = self.embedder.embed(["test text"])
        vec = result[0]
        norm = math.sqrt(sum(v * v for v in vec))
        self.assertAlmostEqual(norm, 1.0, places=5)


# ---------------------------------------------------------------------------
# KeywordStubEmbedder._tokenize
# ---------------------------------------------------------------------------

class TestKeywordStubEmbedderTokenize(unittest.TestCase):
    """Tests for KeywordStubEmbedder._tokenize() — simple regex tokenizer."""

    def setUp(self):
        self.embedder = te.KeywordStubEmbedder(dim=64)

    def test_basic_tokens(self):
        result = self.embedder._tokenize("hello world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_short_tokens_excluded(self):
        # Pattern is r"[a-zA-Z0-9_]{3,}" — min 3 chars
        result = self.embedder._tokenize("hi go run foo bar")
        self.assertNotIn("hi", result)
        self.assertNotIn("go", result)

    def test_lowercased(self):
        result = self.embedder._tokenize("Hello World")
        self.assertIn("hello", result)
        self.assertNotIn("Hello", result)

    def test_punctuation_excluded(self):
        result = self.embedder._tokenize("hello, world!")
        self.assertIn("hello", result)
        self.assertIn("world", result)
        # No punctuation tokens
        for tok in result:
            self.assertNotIn(",", tok)

    def test_returns_list(self):
        self.assertIsInstance(self.embedder._tokenize("test"), list)

    def test_empty_string_returns_empty(self):
        self.assertEqual(self.embedder._tokenize(""), [])


# ---------------------------------------------------------------------------
# KeywordStubEmbedder.embed
# ---------------------------------------------------------------------------

class TestKeywordStubEmbedderEmbed(unittest.TestCase):
    """Tests for KeywordStubEmbedder.embed() — bag-of-words hash embeddings."""

    def setUp(self):
        self.embedder = te.KeywordStubEmbedder(dim=64)

    def test_returns_list_of_vectors(self):
        result = self.embedder.embed(["hello world"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_correct_dim(self):
        result = self.embedder.embed(["active inference"])
        self.assertEqual(len(result[0]), 64)

    def test_deterministic(self):
        a = self.embedder.embed(["test phrase"])
        b = self.embedder.embed(["test phrase"])
        self.assertEqual(a, b)

    def test_multiple_texts(self):
        result = self.embedder.embed(["foo", "bar"])
        self.assertEqual(len(result), 2)

    def test_empty_texts_empty_result(self):
        result = self.embedder.embed([])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
