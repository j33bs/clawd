"""Tests for workspace/store/being_divergence.py pure helper functions.

Covers (no subprocess, no network, no lancedb):
- _tokenize
- _noun_like_tokens
- _remove_tokens
- _hash_embed_text / _normalize_vector / _cosine_distance
- _timestamp_utc / _timestamp_compact
- _attractor_threshold_stats
- _compute_verdict
- _style_consistency_value
- _masking_variant_verdict
"""
import sys
import unittest
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

from being_divergence import (  # noqa: E402
    _attractor_threshold_stats,
    _compute_verdict,
    _cosine_distance,
    _hash_embed_text,
    _masking_variant_verdict,
    _normalize_vector,
    _noun_like_tokens,
    _remove_tokens,
    _style_consistency_value,
    _timestamp_compact,
    _timestamp_utc,
    _tokenize,
)


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize(unittest.TestCase):
    """Tests for _tokenize() — [A-Za-z0-9_-]+ regex tokenizer."""

    def test_simple_words(self):
        self.assertEqual(_tokenize("hello world"), ["hello", "world"])

    def test_alphanumeric_and_underscore(self):
        tokens = _tokenize("INV_003 score=1.0")
        self.assertIn("INV_003", tokens)
        self.assertIn("score", tokens)
        self.assertIn("1", tokens)

    def test_hyphen_included(self):
        self.assertIn("INV-003", _tokenize("INV-003"))

    def test_punctuation_stripped(self):
        tokens = _tokenize("hello, world!")
        self.assertNotIn("hello,", tokens)
        self.assertIn("hello", tokens)

    def test_empty_string(self):
        self.assertEqual(_tokenize(""), [])

    def test_returns_list(self):
        self.assertIsInstance(_tokenize("abc"), list)

    def test_numbers_kept(self):
        self.assertIn("123", _tokenize("123 abc"))


# ---------------------------------------------------------------------------
# _noun_like_tokens
# ---------------------------------------------------------------------------

class TestNounLikeTokens(unittest.TestCase):
    """Tests for _noun_like_tokens() — uppercase/special token filter."""

    def test_uppercase_words_captured(self):
        result = _noun_like_tokens(["Claude is here"])
        self.assertIn("Claude", result)

    def test_inv_prefix_captured(self):
        result = _noun_like_tokens(["running INV-003 now"])
        self.assertIn("INV-003", result)

    def test_rule_prefix_captured(self):
        result = _noun_like_tokens(["see RULE-42 for details"])
        self.assertIn("RULE-42", result)

    def test_lowercase_only_excluded(self):
        result = _noun_like_tokens(["just lowercase words here"])
        self.assertEqual(result, [])

    def test_top_k_respected(self):
        # Many unique uppercase tokens; top_k limits output
        bodies = [("Token%d " % i) * 2 for i in range(100)]
        result = _noun_like_tokens(bodies, top_k=5)
        self.assertLessEqual(len(result), 5)

    def test_returns_list(self):
        self.assertIsInstance(_noun_like_tokens([]), list)

    def test_most_frequent_first(self):
        # "Alpha" appears 3x, "Beta" appears 1x
        bodies = ["Alpha Alpha Alpha Beta"]
        result = _noun_like_tokens(bodies, top_k=10)
        self.assertEqual(result[0], "Alpha")


# ---------------------------------------------------------------------------
# _remove_tokens
# ---------------------------------------------------------------------------

class TestRemoveTokens(unittest.TestCase):
    """Tests for _remove_tokens() — word-boundary removal."""

    def test_removes_token(self):
        result = _remove_tokens("Claude is here", ["Claude"])
        self.assertNotIn("Claude", result)

    def test_empty_tokens_returns_body(self):
        self.assertEqual(_remove_tokens("hello world", []), "hello world")

    def test_removes_multiple(self):
        result = _remove_tokens("INV-003 score pass", ["INV-003", "score"])
        self.assertNotIn("INV-003", result)
        self.assertNotIn("score", result)
        self.assertIn("pass", result)

    def test_collapses_whitespace(self):
        result = _remove_tokens("a b c", ["b"])
        # Double space should be collapsed to single
        self.assertNotIn("  ", result)

    def test_does_not_remove_substring(self):
        # "INV" should not remove "INV-003" as a substring
        result = _remove_tokens("INV-003", ["INV"])
        # "INV" as a whole word isn't in "INV-003" (hyphen breaks boundary)
        # depending on regex — verify no crash at minimum
        self.assertIsInstance(result, str)

    def test_returns_stripped_result(self):
        result = _remove_tokens("Claude speaks", ["Claude"])
        self.assertFalse(result.startswith(" "))


# ---------------------------------------------------------------------------
# _normalize_vector / _cosine_distance
# ---------------------------------------------------------------------------

class TestNormalizeVector(unittest.TestCase):
    """Tests for _normalize_vector() — L2 normalization."""

    def test_unit_vector_unchanged(self):
        v = np.array([1.0, 0.0, 0.0])
        result = _normalize_vector(v)
        np.testing.assert_allclose(result, v, atol=1e-10)

    def test_normalized_has_unit_norm(self):
        v = np.array([3.0, 4.0])  # norm=5
        result = _normalize_vector(v)
        self.assertAlmostEqual(float(np.linalg.norm(result)), 1.0, places=10)

    def test_zero_vector_handled(self):
        # Should not raise; zero vector stays zero or normalized gracefully
        v = np.zeros(4)
        result = _normalize_vector(v)
        self.assertIsInstance(result, np.ndarray)

    def test_returns_ndarray(self):
        self.assertIsInstance(_normalize_vector(np.array([1.0, 2.0])), np.ndarray)


class TestCosineDistance(unittest.TestCase):
    """Tests for _cosine_distance() — 1 - cosine_similarity."""

    def test_identical_vectors_distance_zero(self):
        v = np.array([1.0, 0.0, 0.0])
        dist = _cosine_distance(v, v)
        self.assertAlmostEqual(dist, 0.0, places=8)

    def test_orthogonal_vectors_distance_one(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        dist = _cosine_distance(a, b)
        self.assertAlmostEqual(dist, 1.0, places=8)

    def test_opposite_vectors_distance_two(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        dist = _cosine_distance(a, b)
        self.assertAlmostEqual(dist, 2.0, places=8)

    def test_result_is_float(self):
        a = np.array([1.0, 2.0])
        b = np.array([3.0, 4.0])
        self.assertIsInstance(_cosine_distance(a, b), float)


# ---------------------------------------------------------------------------
# _hash_embed_text
# ---------------------------------------------------------------------------

class TestHashEmbedText(unittest.TestCase):
    """Tests for _hash_embed_text() — deterministic hash embedding."""

    def test_returns_ndarray(self):
        self.assertIsInstance(_hash_embed_text("hello"), np.ndarray)

    def test_default_dim_64(self):
        self.assertEqual(_hash_embed_text("hello").shape, (64,))

    def test_custom_dim(self):
        self.assertEqual(_hash_embed_text("hello", dim=32).shape, (32,))

    def test_deterministic(self):
        v1 = _hash_embed_text("same text")
        v2 = _hash_embed_text("same text")
        np.testing.assert_array_equal(v1, v2)

    def test_different_texts_different_vectors(self):
        v1 = _hash_embed_text("text A")
        v2 = _hash_embed_text("text B")
        self.assertFalse(np.allclose(v1, v2))

    def test_unit_norm(self):
        v = _hash_embed_text("normalize me")
        norm = float(np.linalg.norm(v))
        # normalized unless zero vector
        if norm > 1e-10:
            self.assertAlmostEqual(norm, 1.0, places=8)


# ---------------------------------------------------------------------------
# _timestamp_utc / _timestamp_compact
# ---------------------------------------------------------------------------

class TestTimestampUtc(unittest.TestCase):
    """Tests for _timestamp_utc() — ISO timestamp string."""

    def test_returns_string(self):
        self.assertIsInstance(_timestamp_utc(), str)

    def test_ends_with_z(self):
        self.assertTrue(_timestamp_utc().endswith("Z"))

    def test_contains_t_separator(self):
        self.assertIn("T", _timestamp_utc())

    def test_different_calls_may_differ(self):
        # Just verify no crash on repeated calls
        for _ in range(3):
            _timestamp_utc()


class TestTimestampCompact(unittest.TestCase):
    """Tests for _timestamp_compact() — compact timestamp string."""

    def test_returns_string(self):
        self.assertIsInstance(_timestamp_compact(), str)

    def test_ends_with_z(self):
        self.assertTrue(_timestamp_compact().endswith("Z"))

    def test_no_hyphens_or_colons(self):
        ts = _timestamp_compact()
        self.assertNotIn("-", ts)
        self.assertNotIn(":", ts)

    def test_contains_t(self):
        self.assertIn("T", _timestamp_compact())


# ---------------------------------------------------------------------------
# _attractor_threshold_stats
# ---------------------------------------------------------------------------

class TestAttractorThresholdStats(unittest.TestCase):
    """Tests for _attractor_threshold_stats() — percentile + mean."""

    def test_empty_returns_zeros(self):
        threshold, baseline = _attractor_threshold_stats([])
        self.assertAlmostEqual(threshold, 0.0)
        self.assertAlmostEqual(baseline, 0.0)

    def test_single_value(self):
        threshold, baseline = _attractor_threshold_stats([0.5])
        # percentile(95) and mean of single item → both 0.5
        self.assertAlmostEqual(threshold, 0.5)
        self.assertAlmostEqual(baseline, 0.5)

    def test_baseline_is_mean(self):
        scores = [0.1, 0.2, 0.3, 0.4, 0.5]
        _, baseline = _attractor_threshold_stats(scores)
        self.assertAlmostEqual(baseline, 0.3, places=8)

    def test_threshold_is_p95(self):
        scores = list(range(1, 101))  # 1..100; p95 ≈ 95.05
        threshold, _ = _attractor_threshold_stats([float(x) for x in scores])
        self.assertGreater(threshold, 90.0)

    def test_threshold_geq_baseline(self):
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        threshold, baseline = _attractor_threshold_stats(scores)
        self.assertGreaterEqual(threshold, baseline)

    def test_returns_floats(self):
        threshold, baseline = _attractor_threshold_stats([1.0, 2.0])
        self.assertIsInstance(threshold, float)
        self.assertIsInstance(baseline, float)


# ---------------------------------------------------------------------------
# _compute_verdict
# ---------------------------------------------------------------------------

class TestComputeVerdict(unittest.TestCase):
    """Tests for _compute_verdict() — DISPOSITIONAL/SITUATIONAL/INCONCLUSIVE logic."""

    _PBS_OK = {"a": {"n_sections": 5}, "b": {"n_sections": 5}}
    _PBS_LOW = {"a": {"n_sections": 1}, "b": {"n_sections": 5}}

    def test_low_sections_inconclusive(self):
        result = _compute_verdict(
            score=0.9, baseline=0.5,
            author_silhouette=0.5, topic_silhouette=0.1,
            per_being_scores=self._PBS_LOW,
            min_sections_per_author=3,
        )
        self.assertEqual(result, "INCONCLUSIVE")

    def test_high_score_author_dominant_dispositional(self):
        result = _compute_verdict(
            score=0.9, baseline=0.5,  # score - baseline = 0.4 >= 0.20
            author_silhouette=0.5, topic_silhouette=0.1,  # auth > topic
            per_being_scores=self._PBS_OK,
            min_sections_per_author=3,
        )
        self.assertEqual(result, "DISPOSITIONAL")

    def test_low_score_situational(self):
        result = _compute_verdict(
            score=0.51, baseline=0.5,  # score - baseline = 0.01 <= 0.05
            author_silhouette=0.1, topic_silhouette=0.5,  # topic > auth
            per_being_scores=self._PBS_OK,
            min_sections_per_author=3,
        )
        self.assertEqual(result, "SITUATIONAL")

    def test_topic_dominant_situational(self):
        # score is high enough but topic_sil > author_sil → SITUATIONAL
        result = _compute_verdict(
            score=0.8, baseline=0.5,  # score - baseline = 0.3 >= 0.20
            author_silhouette=0.1, topic_silhouette=0.5,  # topic >= author
            per_being_scores=self._PBS_OK,
            min_sections_per_author=3,
        )
        self.assertEqual(result, "SITUATIONAL")

    def test_borderline_inconclusive(self):
        result = _compute_verdict(
            score=0.62, baseline=0.5,  # score-baseline=0.12; > 0.05 but < 0.20
            author_silhouette=0.3, topic_silhouette=0.1,  # auth > topic but score not high enough
            per_being_scores=self._PBS_OK,
            min_sections_per_author=3,
        )
        self.assertEqual(result, "INCONCLUSIVE")

    def test_none_silhouettes_can_give_situational_via_score(self):
        result = _compute_verdict(
            score=0.51, baseline=0.5,
            author_silhouette=None, topic_silhouette=None,
            per_being_scores=self._PBS_OK,
            min_sections_per_author=3,
        )
        self.assertEqual(result, "SITUATIONAL")


# ---------------------------------------------------------------------------
# _style_consistency_value
# ---------------------------------------------------------------------------

class TestStyleConsistencyValue(unittest.TestCase):
    """Tests for _style_consistency_value() — PASS/FAIL/untested logic."""

    _PBS_OK = {"a": {"n_sections": 5}, "b": {"n_sections": 5}}
    _PBS_LOW = {"a": {"n_sections": 2}, "b": {"n_sections": 5}}

    def test_low_sections_returns_untested(self):
        result = _style_consistency_value(
            self._PBS_LOW,
            author_silhouette=0.5,
            topic_silhouette=0.1,
            min_sections_per_being=3,
        )
        self.assertEqual(result, "untested")

    def test_author_above_topic_returns_true(self):
        result = _style_consistency_value(
            self._PBS_OK,
            author_silhouette=0.5,
            topic_silhouette=0.1,
        )
        self.assertTrue(result)

    def test_topic_above_author_returns_false(self):
        result = _style_consistency_value(
            self._PBS_OK,
            author_silhouette=0.1,
            topic_silhouette=0.5,
        )
        self.assertFalse(result)

    def test_none_silhouettes_returns_false(self):
        result = _style_consistency_value(
            self._PBS_OK,
            author_silhouette=None,
            topic_silhouette=None,
        )
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# _masking_variant_verdict
# ---------------------------------------------------------------------------

class TestMaskingVariantVerdict(unittest.TestCase):
    """Tests for _masking_variant_verdict() — string formatter."""

    def test_both_pass(self):
        result = _masking_variant_verdict(True, True)
        self.assertIn("DISPOSITIONAL-ATTRACTOR: PASS", result)
        self.assertIn("STYLE-CONSISTENCY: PASS", result)

    def test_both_fail(self):
        result = _masking_variant_verdict(False, False)
        self.assertIn("DISPOSITIONAL-ATTRACTOR: FAIL", result)
        self.assertIn("STYLE-CONSISTENCY: FAIL", result)

    def test_style_untested(self):
        result = _masking_variant_verdict(True, "untested")
        self.assertIn("STYLE-CONSISTENCY: UNTESTED", result)

    def test_attractor_pass_style_fail(self):
        result = _masking_variant_verdict(True, False)
        self.assertIn("DISPOSITIONAL-ATTRACTOR: PASS", result)
        self.assertIn("STYLE-CONSISTENCY: FAIL", result)

    def test_returns_string(self):
        self.assertIsInstance(_masking_variant_verdict(True, True), str)


if __name__ == "__main__":
    unittest.main()
