"""Tests for adversarial_probe — generate_nonsense_r1, generate_mirror_r1,
generate_filler_r1, _cosine_sim, DOMAIN_ANTONYMS, FILLER_POOL."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import adversarial_probe as ap


class TestCosineSim(unittest.TestCase):
    """Tests for _cosine_sim() — dot-product cosine similarity."""

    def test_identical_returns_one(self):
        a = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(ap._cosine_sim(a, a), 1.0, places=6)

    def test_orthogonal_returns_zero(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(ap._cosine_sim(a, b), 0.0, places=6)

    def test_opposite_returns_minus_one(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        self.assertAlmostEqual(ap._cosine_sim(a, b), -1.0, places=6)

    def test_zero_norm_returns_zero(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        # norm_a < 1e-12 → return 0.0
        self.assertAlmostEqual(ap._cosine_sim(a, b), 0.0, places=6)

    def test_symmetric(self):
        a = [0.3, 0.7, 0.5]
        b = [0.9, 0.1, 0.2]
        self.assertAlmostEqual(ap._cosine_sim(a, b), ap._cosine_sim(b, a), places=6)

    def test_scaled_same_direction_returns_one(self):
        a = [1.0, 2.0]
        b = [3.0, 6.0]  # 3 * a
        self.assertAlmostEqual(ap._cosine_sim(a, b), 1.0, places=6)


class TestGenerateNonsenseR1(unittest.TestCase):
    """Tests for generate_nonsense_r1() — deterministic synthetic adversarial text."""

    def test_returns_string(self):
        result = ap.generate_nonsense_r1()
        self.assertIsInstance(result, str)

    def test_not_empty(self):
        result = ap.generate_nonsense_r1()
        self.assertGreater(len(result), 0)

    def test_deterministic_with_same_seed(self):
        r1 = ap.generate_nonsense_r1(seed=42)
        r2 = ap.generate_nonsense_r1(seed=42)
        self.assertEqual(r1, r2)

    def test_different_seeds_produce_different_text(self):
        r1 = ap.generate_nonsense_r1(seed=1)
        r2 = ap.generate_nonsense_r1(seed=2)
        self.assertNotEqual(r1, r2)

    def test_approximately_n_words(self):
        # n_words is approximate (sentences add up to at least n_words)
        result = ap.generate_nonsense_r1(n_words=50, seed=7)
        word_count = len(result.split())
        # Allow generous range since sentences overshoot slightly
        self.assertGreater(word_count, 30)
        self.assertLess(word_count, 200)

    def test_contains_at_least_one_sentence(self):
        result = ap.generate_nonsense_r1(seed=42)
        self.assertIn(".", result)

    def test_first_word_capitalized(self):
        result = ap.generate_nonsense_r1(seed=42)
        first_char = result.lstrip()[0]
        self.assertTrue(first_char.isupper(), f"Expected uppercase, got: {first_char!r}")

    def test_uses_words_from_filler_pool_or_antonyms(self):
        result = ap.generate_nonsense_r1(seed=42).lower()
        pool_words = set(ap.FILLER_POOL) | set(ap.DOMAIN_ANTONYMS.keys()) | set(ap.DOMAIN_ANTONYMS.values())
        # At least one pool word should appear in the output
        found = any(w in result for w in pool_words)
        self.assertTrue(found, "Expected at least one filler/antonym word in output")


class TestGenerateMirrorR1(unittest.TestCase):
    """Tests for generate_mirror_r1() — domain term negation strategy."""

    def test_returns_string(self):
        result = ap.generate_mirror_r1("The convergence is stable.")
        self.assertIsInstance(result, str)

    def test_replaces_domain_terms(self):
        # "convergence" → "divergence" (from DOMAIN_ANTONYMS)
        result = ap.generate_mirror_r1("The convergence is stable.")
        self.assertIn("divergence", result)

    def test_replaces_multiple_terms(self):
        text = "The stable local convergence is valid."
        result = ap.generate_mirror_r1(text)
        self.assertIn("chaotic", result)   # stable → chaotic
        self.assertIn("remote", result)    # local → remote
        self.assertIn("divergence", result)  # convergence → divergence

    def test_negation_prefix_prepended(self):
        result = ap.generate_mirror_r1("some text")
        self.assertIn("In contrast", result)

    def test_negation_suffix_appended(self):
        result = ap.generate_mirror_r1("some text")
        self.assertIn("None of the above claims", result)

    def test_no_brackets_in_output(self):
        result = ap.generate_mirror_r1("convergence stable novel")
        self.assertNotIn("[[", result)
        self.assertNotIn("]]", result)

    def test_source_not_in_output_after_replacement(self):
        # "convergence" should NOT appear since it's replaced
        result = ap.generate_mirror_r1("convergence")
        self.assertNotIn("convergence", result)

    def test_unknown_words_unchanged(self):
        result = ap.generate_mirror_r1("banana pineapple mango")
        self.assertIn("banana", result)
        self.assertIn("pineapple", result)
        self.assertIn("mango", result)


class TestGenerateFillerR1(unittest.TestCase):
    """Tests for generate_filler_r1() — template-based syntactic filler."""

    def test_returns_string(self):
        result = ap.generate_filler_r1()
        self.assertIsInstance(result, str)

    def test_not_empty(self):
        result = ap.generate_filler_r1()
        self.assertGreater(len(result), 0)

    def test_deterministic_with_same_seed(self):
        r1 = ap.generate_filler_r1(seed=99)
        r2 = ap.generate_filler_r1(seed=99)
        self.assertEqual(r1, r2)

    def test_different_seeds_produce_different_text(self):
        r1 = ap.generate_filler_r1(seed=1)
        r2 = ap.generate_filler_r1(seed=2)
        self.assertNotEqual(r1, r2)

    def test_contains_sentences_with_periods(self):
        result = ap.generate_filler_r1(length=50, seed=99)
        self.assertIn(".", result)

    def test_contains_filler_pool_words(self):
        result = ap.generate_filler_r1(length=200, seed=99).lower()
        found = any(w.lower() in result for w in ap.FILLER_POOL)
        self.assertTrue(found)

    def test_longer_length_produces_more_text(self):
        short = ap.generate_filler_r1(length=30, seed=5)
        long = ap.generate_filler_r1(length=150, seed=5)
        self.assertGreater(len(long), len(short))


class TestDomainAntonyms(unittest.TestCase):
    """Tests for DOMAIN_ANTONYMS — coverage and structure."""

    def test_is_dict(self):
        self.assertIsInstance(ap.DOMAIN_ANTONYMS, dict)

    def test_non_empty(self):
        self.assertGreater(len(ap.DOMAIN_ANTONYMS), 0)

    def test_convergence_divergence(self):
        self.assertEqual(ap.DOMAIN_ANTONYMS.get("convergence"), "divergence")

    def test_stable_chaotic(self):
        self.assertEqual(ap.DOMAIN_ANTONYMS.get("stable"), "chaotic")

    def test_all_keys_lowercase(self):
        for k in ap.DOMAIN_ANTONYMS:
            self.assertEqual(k, k.lower(), f"Key not lowercase: {k!r}")

    def test_all_values_nonempty_strings(self):
        for k, v in ap.DOMAIN_ANTONYMS.items():
            self.assertIsInstance(v, str)
            self.assertGreater(len(v), 0)


if __name__ == "__main__":
    unittest.main()
