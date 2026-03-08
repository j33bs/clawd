"""Tests for pure helpers in workspace/memory_ext/local_rag.py.

Uses sys.path to load via the real _common module.
Covers:
- _tokenize
- _cosine_similarity
- LocalEmbedder._hash_embed
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEM_EXT_DIR = REPO_ROOT / "workspace" / "memory_ext"

if str(MEM_EXT_DIR) not in sys.path:
    sys.path.insert(0, str(MEM_EXT_DIR))

from local_rag import _tokenize, _cosine_similarity, LocalEmbedder  # noqa: E402


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize(unittest.TestCase):
    """Tests for _tokenize() — whitespace split with lowercase + filter empty."""

    def test_basic_tokenization(self):
        result = _tokenize("Hello World")
        self.assertEqual(result, ["hello", "world"])

    def test_empty_string_returns_empty(self):
        self.assertEqual(_tokenize(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(_tokenize(None), [])

    def test_preserves_all_tokens(self):
        result = _tokenize("one two three")
        self.assertEqual(len(result), 3)

    def test_returns_list(self):
        self.assertIsInstance(_tokenize("text"), list)

    def test_multiple_spaces_handled(self):
        result = _tokenize("a  b   c")
        self.assertEqual(result, ["a", "b", "c"])


# ---------------------------------------------------------------------------
# _cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity(unittest.TestCase):
    """Tests for _cosine_similarity() — cosine between two float vectors."""

    def test_identical_vectors_one(self):
        v = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(_cosine_similarity(v, v), 1.0)

    def test_zero_vector_returns_zero(self):
        self.assertAlmostEqual(_cosine_similarity([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_orthogonal_returns_zero(self):
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_returns_minus_one(self):
        self.assertAlmostEqual(_cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_empty_list_returns_zero(self):
        self.assertAlmostEqual(_cosine_similarity([], [1.0, 2.0]), 0.0)

    def test_mismatched_lengths_returns_zero(self):
        self.assertAlmostEqual(_cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(_cosine_similarity([1.0], [1.0]), float)

    def test_known_value(self):
        # [3,4] · [3,4] / (5 * 5) = 1.0
        self.assertAlmostEqual(_cosine_similarity([3.0, 4.0], [3.0, 4.0]), 1.0)


# ---------------------------------------------------------------------------
# LocalEmbedder._hash_embed
# ---------------------------------------------------------------------------

class TestLocalEmbedderHashEmbed(unittest.TestCase):
    """Tests for LocalEmbedder._hash_embed() — deterministic hash embedding."""

    def setUp(self):
        self.embedder = LocalEmbedder(dim=64)

    def test_returns_list(self):
        result = self.embedder._hash_embed("hello world")
        self.assertIsInstance(result, list)

    def test_correct_dimension(self):
        result = self.embedder._hash_embed("text")
        self.assertEqual(len(result), 64)

    def test_deterministic(self):
        a = self.embedder._hash_embed("same text")
        b = self.embedder._hash_embed("same text")
        self.assertEqual(a, b)

    def test_empty_returns_zeros(self):
        result = self.embedder._hash_embed("")
        self.assertEqual(result, [0.0] * 64)

    def test_different_texts_differ(self):
        a = self.embedder._hash_embed("apple")
        b = self.embedder._hash_embed("banana")
        self.assertNotEqual(a, b)

    def test_custom_dim(self):
        e32 = LocalEmbedder(dim=32)
        result = e32._hash_embed("test")
        self.assertEqual(len(result), 32)


if __name__ == "__main__":
    unittest.main()
