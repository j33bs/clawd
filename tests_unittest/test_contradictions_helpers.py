"""Tests for workspace/hivemind/hivemind/intelligence/contradictions.py pure helpers.

Covers (no I/O, no network):
- _tokens
- _sim
- _has_negation
- _iso
- _ku_id
- _make_report
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRAD_DIR = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "intelligence"
if str(CONTRAD_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRAD_DIR))

from contradictions import (  # noqa: E402
    _has_negation,
    _iso,
    _ku_id,
    _make_report,
    _sim,
    _tokens,
)


# ---------------------------------------------------------------------------
# _tokens
# ---------------------------------------------------------------------------

class TestTokens(unittest.TestCase):
    """Tests for _tokens() — alphanumeric tokenizer."""

    def test_simple_words(self):
        self.assertEqual(_tokens("hello world"), ["hello", "world"])

    def test_lowercased(self):
        result = _tokens("Hello World")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_alphanumeric_kept(self):
        result = _tokens("test123")
        self.assertIn("test123", result)

    def test_punctuation_stripped(self):
        result = _tokens("hello, world!")
        self.assertNotIn("hello,", result)
        self.assertIn("hello", result)

    def test_hyphen_kept(self):
        self.assertIn("do-not", _tokens("do-not"))

    def test_empty_returns_empty(self):
        self.assertEqual(_tokens(""), [])

    def test_returns_list(self):
        self.assertIsInstance(_tokens("abc"), list)


# ---------------------------------------------------------------------------
# _sim
# ---------------------------------------------------------------------------

class TestSim(unittest.TestCase):
    """Tests for _sim() — cosine similarity on token bags."""

    def test_identical_texts_score_1(self):
        self.assertAlmostEqual(_sim("alpha beta", "alpha beta"), 1.0)

    def test_disjoint_texts_score_0(self):
        self.assertAlmostEqual(_sim("aaa bbb", "ccc ddd"), 0.0)

    def test_partial_overlap_between_0_and_1(self):
        val = _sim("alpha beta", "alpha gamma")
        self.assertGreater(val, 0.0)
        self.assertLess(val, 1.0)

    def test_empty_text_returns_0(self):
        self.assertAlmostEqual(_sim("", "anything"), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(_sim("hello", "hello"), float)

    def test_symmetry(self):
        a, b = "foo bar", "bar baz"
        self.assertAlmostEqual(_sim(a, b), _sim(b, a))


# ---------------------------------------------------------------------------
# _has_negation
# ---------------------------------------------------------------------------

class TestHasNegation(unittest.TestCase):
    """Tests for _has_negation() — detects negation tokens."""

    def test_not_detected(self):
        self.assertTrue(_has_negation("do not do this"))

    def test_never_detected(self):
        self.assertTrue(_has_negation("never trust this"))

    def test_cannot_detected(self):
        self.assertTrue(_has_negation("you cannot proceed"))

    def test_no_keyword_returns_false(self):
        self.assertFalse(_has_negation("proceed with the plan"))

    def test_empty_returns_false(self):
        self.assertFalse(_has_negation(""))

    def test_avoid_detected(self):
        self.assertTrue(_has_negation("avoid this pattern"))

    def test_returns_bool(self):
        self.assertIsInstance(_has_negation("text"), bool)


# ---------------------------------------------------------------------------
# _iso
# ---------------------------------------------------------------------------

class TestIso(unittest.TestCase):
    """Tests for _iso() — ISO timestamp string → UTC-aware datetime."""

    def test_returns_datetime(self):
        result = _iso("2026-01-15T12:00:00")
        self.assertIsInstance(result, datetime)

    def test_naive_becomes_utc(self):
        result = _iso("2026-01-15T12:00:00")
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_z_suffix_parsed(self):
        result = _iso("2026-01-15T12:00:00+00:00")
        self.assertEqual(result.hour, 12)

    def test_year_month_day(self):
        result = _iso("2026-03-08T10:30:00")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 8)


# ---------------------------------------------------------------------------
# _ku_id
# ---------------------------------------------------------------------------

class TestKuId(unittest.TestCase):
    """Tests for _ku_id() — deterministic ID from KU dict."""

    def test_returns_string(self):
        self.assertIsInstance(_ku_id({"content_hash": "abc123"}), str)

    def test_starts_with_ku_(self):
        result = _ku_id({"source": "test", "content": "hello"})
        self.assertTrue(result.startswith("ku_"))

    def test_same_ku_same_id(self):
        ku = {"source": "test", "content": "hello world"}
        self.assertEqual(_ku_id(ku), _ku_id(ku))

    def test_different_content_different_id(self):
        ku1 = {"source": "test", "content": "hello"}
        ku2 = {"source": "test", "content": "world"}
        self.assertNotEqual(_ku_id(ku1), _ku_id(ku2))

    def test_content_hash_takes_priority(self):
        ku = {"content_hash": "deadbeef123456789012"}
        result = _ku_id(ku)
        self.assertIn("deadbeef", result)

    def test_empty_ku_returns_string(self):
        self.assertIsInstance(_ku_id({}), str)


# ---------------------------------------------------------------------------
# _make_report
# ---------------------------------------------------------------------------

class TestMakeReport(unittest.TestCase):
    """Tests for _make_report() — contradiction report dict."""

    _KU_A = {"source": "test", "content": "alpha", "created_at": "2026-01-01T00:00:00"}
    _KU_B = {"source": "test", "content": "beta", "created_at": "2026-01-02T00:00:00"}

    def test_returns_dict(self):
        result = _make_report(self._KU_A, self._KU_B, reason="test", severity="warning")
        self.assertIsInstance(result, dict)

    def test_id_present(self):
        result = _make_report(self._KU_A, self._KU_B, reason="test", severity="warning")
        self.assertIn("id", result)
        self.assertTrue(result["id"].startswith("contradiction_"))

    def test_severity_preserved(self):
        result = _make_report(self._KU_A, self._KU_B, reason="r", severity="critical")
        self.assertEqual(result["severity"], "critical")

    def test_reason_preserved(self):
        result = _make_report(self._KU_A, self._KU_B, reason="Fact collision", severity="warning")
        self.assertEqual(result["reason"], "Fact collision")

    def test_ku_ids_sorted(self):
        result = _make_report(self._KU_A, self._KU_B, reason="r", severity="warning")
        ids = result["ku_ids"]
        self.assertEqual(ids, sorted(ids))

    def test_deterministic(self):
        r1 = _make_report(self._KU_A, self._KU_B, reason="r", severity="warning")
        r2 = _make_report(self._KU_A, self._KU_B, reason="r", severity="warning")
        self.assertEqual(r1["id"], r2["id"])

    def test_flagged_for_review_present(self):
        result = _make_report(self._KU_A, self._KU_B, reason="r", severity="warning")
        self.assertIn("flagged_for_review", result)


if __name__ == "__main__":
    unittest.main()
