"""Tests for workspace/memory_ext/phi_tracker.py pure helper functions.

Covers (no file I/O beyond env-gated log_phi):
- _token_set
- _jaccard
- measure_coherence
- measure_integration
- phi_score
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.phi_tracker import (  # noqa: E402
    _jaccard,
    _token_set,
    measure_coherence,
    measure_integration,
    phi_score,
)


# ---------------------------------------------------------------------------
# _token_set
# ---------------------------------------------------------------------------

class TestTokenSet(unittest.TestCase):
    """Tests for _token_set() — text → set of lowercase tokens."""

    def test_simple_words(self):
        result = _token_set("hello world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_lowercased(self):
        result = _token_set("Hello World")
        self.assertIn("hello", result)

    def test_empty_returns_empty_set(self):
        self.assertEqual(_token_set(""), set())

    def test_none_safe(self):
        result = _token_set(None)
        self.assertIsInstance(result, set)

    def test_returns_set(self):
        self.assertIsInstance(_token_set("abc"), set)


# ---------------------------------------------------------------------------
# _jaccard
# ---------------------------------------------------------------------------

class TestJaccard(unittest.TestCase):
    """Tests for _jaccard() — set intersection / union ratio."""

    def test_identical_sets_score_1(self):
        s = {"a", "b", "c"}
        self.assertAlmostEqual(_jaccard(s, s), 1.0)

    def test_disjoint_sets_score_0(self):
        self.assertAlmostEqual(_jaccard({"a", "b"}, {"c", "d"}), 0.0)

    def test_partial_overlap(self):
        val = _jaccard({"a", "b"}, {"b", "c"})
        self.assertGreater(val, 0.0)
        self.assertLess(val, 1.0)

    def test_both_empty_score_1(self):
        self.assertAlmostEqual(_jaccard(set(), set()), 1.0)

    def test_one_empty_score_0(self):
        self.assertAlmostEqual(_jaccard({"a"}, set()), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(_jaccard({"a"}, {"a"}), float)


# ---------------------------------------------------------------------------
# measure_coherence
# ---------------------------------------------------------------------------

class TestMeasureCoherence(unittest.TestCase):
    """Tests for measure_coherence() — adjacent-pair Jaccard mean."""

    def test_empty_sections_returns_0(self):
        self.assertAlmostEqual(measure_coherence([]), 0.0)

    def test_single_section_returns_1(self):
        self.assertAlmostEqual(measure_coherence(["only one"]), 1.0)

    def test_identical_sections_return_1(self):
        sections = ["alpha beta", "alpha beta"]
        self.assertAlmostEqual(measure_coherence(sections), 1.0)

    def test_disjoint_sections_return_0(self):
        sections = ["aaa bbb", "ccc ddd"]
        self.assertAlmostEqual(measure_coherence(sections), 0.0)

    def test_result_in_unit_interval(self):
        val = measure_coherence(["hello world", "world peace", "peace talks"])
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(measure_coherence(["a b", "c d"]), float)


# ---------------------------------------------------------------------------
# measure_integration
# ---------------------------------------------------------------------------

class TestMeasureIntegration(unittest.TestCase):
    """Tests for measure_integration() — left-half vs right-half Jaccard."""

    def test_empty_returns_0(self):
        self.assertAlmostEqual(measure_integration([]), 0.0)

    def test_identical_halves_return_1(self):
        sections = ["alpha beta", "alpha beta"]
        self.assertAlmostEqual(measure_integration(sections), 1.0)

    def test_disjoint_halves_return_0(self):
        sections = ["aaa bbb", "ccc ddd"]
        self.assertAlmostEqual(measure_integration(sections), 0.0)

    def test_result_in_unit_interval(self):
        val = measure_integration(["hello world", "world peace", "peace talks"])
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(measure_integration(["a", "b"]), float)


# ---------------------------------------------------------------------------
# phi_score
# ---------------------------------------------------------------------------

class TestPhiScore(unittest.TestCase):
    """Tests for phi_score() — composite Φ metric dict."""

    def test_returns_dict(self):
        self.assertIsInstance(phi_score(["hello", "world"]), dict)

    def test_phi_key_present(self):
        result = phi_score(["a b", "b c"])
        self.assertIn("phi", result)

    def test_components_key_present(self):
        result = phi_score(["a b", "b c"])
        self.assertIn("components", result)

    def test_components_has_coherence(self):
        result = phi_score(["a b", "b c"])
        self.assertIn("coherence", result["components"])

    def test_phi_in_unit_interval(self):
        result = phi_score(["alpha beta gamma", "gamma delta epsilon"])
        self.assertGreaterEqual(result["phi"], 0.0)
        self.assertLessEqual(result["phi"], 1.0)

    def test_empty_sections_phi_0(self):
        result = phi_score([])
        self.assertAlmostEqual(result["phi"], 0.0)

    def test_components_has_integration(self):
        result = phi_score(["a b", "b c"])
        self.assertIn("integration", result["components"])

    def test_components_has_novelty_proxy(self):
        result = phi_score(["a b", "b c"])
        self.assertIn("novelty_proxy", result["components"])


if __name__ == "__main__":
    unittest.main()
