import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from memory_ext.phi_tracker import (  # noqa: E402
    _jaccard,
    _token_set,
    log_phi,
    measure_coherence,
    measure_integration,
    phi_score,
)


class TestMemoryExtPhi(unittest.TestCase):
    def test_phi_score_range_stable(self):
        sections = ["alpha beta", "alpha gamma", "gamma delta"]
        first = phi_score(sections)
        second = phi_score(sections)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first["phi"], 0.0)
        self.assertLessEqual(first["phi"], 1.0)

    def test_log_respects_feature_flag(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "workspace" / "state_runtime" / "memory_ext" / "phi_metrics.md"
            with patch.dict(os.environ, {"OPENCLAW_ROOT": td, "OPENCLAW_MEMORY_EXT": "0"}, clear=False):
                log_phi("s1", {"phi": 0.5}, now=datetime(2026, 2, 25, tzinfo=timezone.utc))
                self.assertFalse(target.exists())


# ---------------------------------------------------------------------------
# _token_set
# ---------------------------------------------------------------------------

class TestTokenSet(unittest.TestCase):
    """Tests for _token_set() — whitespace tokenizer returning a set."""

    def test_empty_string_returns_empty_set(self):
        self.assertEqual(_token_set(""), set())

    def test_single_word(self):
        self.assertEqual(_token_set("hello"), {"hello"})

    def test_multiple_words(self):
        result = _token_set("alpha beta gamma")
        self.assertEqual(result, {"alpha", "beta", "gamma"})

    def test_lowercased(self):
        result = _token_set("Hello WORLD")
        self.assertIn("hello", result)
        self.assertIn("world", result)
        self.assertNotIn("Hello", result)

    def test_duplicates_deduplicated(self):
        result = _token_set("a a b")
        self.assertEqual(result, {"a", "b"})

    def test_none_like_empty(self):
        # _token_set coerces to str via str(text or "")
        result = _token_set("")
        self.assertIsInstance(result, set)


# ---------------------------------------------------------------------------
# _jaccard
# ---------------------------------------------------------------------------

class TestJaccard(unittest.TestCase):
    """Tests for _jaccard() — Jaccard similarity between two sets."""

    def test_identical_sets_return_1(self):
        s = {"a", "b", "c"}
        self.assertAlmostEqual(_jaccard(s, s), 1.0)

    def test_disjoint_sets_return_0(self):
        self.assertAlmostEqual(_jaccard({"a", "b"}, {"c", "d"}), 0.0)

    def test_partial_overlap(self):
        a = {"a", "b", "c"}
        b = {"b", "c", "d"}
        # intersection={b,c}=2; union={a,b,c,d}=4 → 0.5
        self.assertAlmostEqual(_jaccard(a, b), 0.5)

    def test_both_empty_returns_1(self):
        # edge case: both empty → 1.0
        self.assertAlmostEqual(_jaccard(set(), set()), 1.0)

    def test_one_empty_returns_0(self):
        self.assertAlmostEqual(_jaccard({"a"}, set()), 0.0)

    def test_symmetry(self):
        a = {"x", "y"}
        b = {"y", "z"}
        self.assertAlmostEqual(_jaccard(a, b), _jaccard(b, a))

    def test_returns_float(self):
        self.assertIsInstance(_jaccard({"a"}, {"a"}), float)


# ---------------------------------------------------------------------------
# measure_coherence
# ---------------------------------------------------------------------------

class TestMeasureCoherence(unittest.TestCase):
    """Tests for measure_coherence() — adjacent Jaccard mean."""

    def test_empty_list_returns_0(self):
        self.assertAlmostEqual(measure_coherence([]), 0.0)

    def test_single_section_returns_1(self):
        self.assertAlmostEqual(measure_coherence(["only one"]), 1.0)

    def test_two_identical_sections_returns_1(self):
        self.assertAlmostEqual(measure_coherence(["alpha beta", "alpha beta"]), 1.0)

    def test_two_disjoint_sections_returns_0(self):
        self.assertAlmostEqual(measure_coherence(["aaa bbb", "ccc ddd"]), 0.0)

    def test_result_in_unit_interval(self):
        val = measure_coherence(["a b", "b c", "c d"])
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_more_overlap_higher_coherence(self):
        high = measure_coherence(["a b c", "a b c", "a b c"])
        low = measure_coherence(["a b c", "x y z", "p q r"])
        self.assertGreater(high, low)


# ---------------------------------------------------------------------------
# measure_integration
# ---------------------------------------------------------------------------

class TestMeasureIntegration(unittest.TestCase):
    """Tests for measure_integration() — Jaccard of left-half vs right-half."""

    def test_empty_list_returns_0(self):
        self.assertAlmostEqual(measure_integration([]), 0.0)

    def test_single_section(self):
        # mid=1; left=sections[:1]; right=sections[1:]=[] → jaccard(set, empty)=0
        val = measure_integration(["alpha beta"])
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_two_identical_sections_returns_1(self):
        self.assertAlmostEqual(measure_integration(["hello world", "hello world"]), 1.0)

    def test_two_disjoint_sections_returns_0(self):
        self.assertAlmostEqual(measure_integration(["aaa bbb", "ccc ddd"]), 0.0)

    def test_result_in_unit_interval(self):
        val = measure_integration(["a b c", "a x y", "b y z", "c x w"])
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(measure_integration(["a b", "c d"]), float)


# ---------------------------------------------------------------------------
# phi_score — composite result dict
# ---------------------------------------------------------------------------

class TestPhiScore(unittest.TestCase):
    """Tests for phi_score() — composite structure and range."""

    def test_returns_dict(self):
        self.assertIsInstance(phi_score(["a b", "b c"]), dict)

    def test_has_phi_key(self):
        self.assertIn("phi", phi_score(["a b", "b c"]))

    def test_has_components_key(self):
        result = phi_score(["a b", "b c"])
        self.assertIn("components", result)

    def test_components_has_coherence_integration_novelty(self):
        comp = phi_score(["a b", "b c"])["components"]
        for key in ("coherence", "integration", "novelty_proxy"):
            self.assertIn(key, comp)

    def test_phi_in_unit_interval(self):
        val = phi_score(["x y z", "y z w", "z w v"])["phi"]
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_empty_list(self):
        result = phi_score([])
        self.assertGreaterEqual(result["phi"], 0.0)
        self.assertLessEqual(result["phi"], 1.0)


if __name__ == "__main__":
    unittest.main()
