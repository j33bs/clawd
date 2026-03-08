"""Tests for hivemind.intelligence submodules — pure functions.

Covers: contradictions._tokens, _sim, _has_negation, _ku_id, _make_report
         summaries._parse_period, _summarize_group
"""
import hashlib
import sys
import unittest
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.intelligence.contradictions import (
    _ku_id, _tokens, _sim, _has_negation, _iso, _NEGATIONS
)
from hivemind.intelligence.summaries import _parse_period, _summarize_group


class TestTokens(unittest.TestCase):
    """Tests for contradictions._tokens() — word-boundary tokenizer."""

    def test_empty_returns_empty(self):
        self.assertEqual(_tokens(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(_tokens(None), [])  # type: ignore[arg-type]

    def test_simple_word(self):
        self.assertIn("hello", _tokens("hello"))

    def test_lowercased(self):
        tokens = _tokens("Hello World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_hyphen_in_token(self):
        tokens = _tokens("co-signed")
        self.assertIn("co-signed", tokens)

    def test_underscore_in_token(self):
        tokens = _tokens("do_not")
        self.assertIn("do_not", tokens)

    def test_punctuation_splits(self):
        tokens = _tokens("hello,world")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_returns_list(self):
        self.assertIsInstance(_tokens("hello"), list)

    def test_numbers_kept(self):
        tokens = _tokens("section42")
        self.assertIn("section42", tokens)


class TestSim(unittest.TestCase):
    """Tests for contradictions._sim() — cosine similarity between two texts."""

    def test_identical_returns_one(self):
        score = _sim("consciousness routing", "consciousness routing")
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_no_overlap_returns_zero(self):
        score = _sim("apple orange", "quantum vacuum")
        self.assertEqual(score, 0.0)

    def test_empty_first_returns_zero(self):
        self.assertEqual(_sim("", "hello world"), 0.0)

    def test_empty_second_returns_zero(self):
        self.assertEqual(_sim("hello world", ""), 0.0)

    def test_partial_overlap_between_zero_and_one(self):
        score = _sim("hello world foo", "hello world bar")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(_sim("a", "b"), float)

    def test_symmetric(self):
        a = "consciousness routing"
        b = "routing mechanisms"
        self.assertAlmostEqual(_sim(a, b), _sim(b, a), places=10)


class TestHasNegation(unittest.TestCase):
    """Tests for contradictions._has_negation() — negation detector."""

    def test_no_negation_returns_false(self):
        self.assertFalse(_has_negation("store memory routing"))

    def test_not_in_text_returns_true(self):
        self.assertTrue(_has_negation("do not route"))

    def test_never_returns_true(self):
        self.assertTrue(_has_negation("never store this"))

    def test_no_word_returns_true(self):
        self.assertTrue(_has_negation("no policy applied"))

    def test_avoid_returns_true(self):
        self.assertTrue(_has_negation("avoid this pattern"))

    def test_cannot_returns_true(self):
        self.assertTrue(_has_negation("cannot process"))

    def test_empty_returns_false(self):
        self.assertFalse(_has_negation(""))

    def test_negations_set_nonempty(self):
        self.assertGreater(len(_NEGATIONS), 0)
        self.assertIsInstance(_NEGATIONS, (set, frozenset))


class TestKuId(unittest.TestCase):
    """Tests for contradictions._ku_id() — stable ID derivation."""

    def test_returns_string(self):
        result = _ku_id({"content_hash": "abc123"})
        self.assertIsInstance(result, str)

    def test_starts_with_ku(self):
        result = _ku_id({"content_hash": "abc123"})
        self.assertTrue(result.startswith("ku_"))

    def test_hash_prefix_used_when_present(self):
        result = _ku_id({"content_hash": "abc123def456"})
        self.assertIn("abc123", result)

    def test_fallback_when_no_hash(self):
        # Should not raise — uses source+content fallback
        result = _ku_id({"source": "test", "content": "hello"})
        self.assertTrue(result.startswith("ku_"))

    def test_same_inputs_same_id(self):
        ku = {"content_hash": "stablechecksum"}
        self.assertEqual(_ku_id(ku), _ku_id(ku))

    def test_different_hashes_different_ids(self):
        id1 = _ku_id({"content_hash": "aaa"})
        id2 = _ku_id({"content_hash": "bbb"})
        self.assertNotEqual(id1, id2)

    def test_empty_dict_doesnt_raise(self):
        result = _ku_id({})
        self.assertIsInstance(result, str)


class TestMakeReport(unittest.TestCase):
    """Tests for contradictions._make_report() — contradiction report structure."""

    def _make_ku(self, hash_val: str, content: str = "some content") -> dict:
        return {"content_hash": hash_val, "content": content, "created_at": "2026-01-01T00:00:00Z"}

    def setUp(self):
        from hivemind.intelligence.contradictions import _make_report
        self._make_report = _make_report

    def test_returns_dict(self):
        ku_a = self._make_ku("aaa")
        ku_b = self._make_ku("bbb")
        result = self._make_report(ku_a, ku_b, reason="high_sim", severity="warning")
        self.assertIsInstance(result, dict)

    def test_id_starts_with_contradiction(self):
        ku_a = self._make_ku("aaa")
        ku_b = self._make_ku("bbb")
        result = self._make_report(ku_a, ku_b, reason="high_sim", severity="warning")
        self.assertTrue(result["id"].startswith("contradiction_"))

    def test_severity_preserved(self):
        ku_a = self._make_ku("aaa")
        ku_b = self._make_ku("bbb")
        result = self._make_report(ku_a, ku_b, reason="high_sim", severity="critical")
        self.assertEqual(result["severity"], "critical")

    def test_reason_preserved(self):
        ku_a = self._make_ku("aaa")
        ku_b = self._make_ku("bbb")
        result = self._make_report(ku_a, ku_b, reason="high_sim", severity="warning")
        self.assertEqual(result["reason"], "high_sim")

    def test_ku_ids_sorted(self):
        ku_a = self._make_ku("zzz")
        ku_b = self._make_ku("aaa")
        result = self._make_report(ku_a, ku_b, reason="x", severity="warning")
        self.assertEqual(result["ku_ids"], sorted(result["ku_ids"]))

    def test_flagged_for_review_by_default(self):
        ku_a = self._make_ku("aaa")
        ku_b = self._make_ku("bbb")
        result = self._make_report(ku_a, ku_b, reason="x", severity="warning")
        self.assertIn("flagged_for_review", result)

    def test_security_note_present(self):
        ku_a = self._make_ku("aaa")
        ku_b = self._make_ku("bbb")
        result = self._make_report(ku_a, ku_b, reason="x", severity="warning")
        self.assertIn("security_note", result)


class TestParsePeriod(unittest.TestCase):
    """Tests for summaries._parse_period() — duration string parsing."""

    def test_days_suffix(self):
        result = _parse_period("7d")
        self.assertEqual(result, timedelta(days=7))

    def test_hours_suffix(self):
        result = _parse_period("24h")
        self.assertEqual(result, timedelta(hours=24))

    def test_unknown_defaults_to_7_days(self):
        result = _parse_period("unknown")
        self.assertEqual(result, timedelta(days=7))

    def test_returns_timedelta(self):
        self.assertIsInstance(_parse_period("7d"), timedelta)

    def test_strips_whitespace(self):
        result = _parse_period("  14d  ")
        self.assertEqual(result, timedelta(days=14))

    def test_case_insensitive(self):
        result = _parse_period("3D")
        self.assertEqual(result, timedelta(days=3))

    def test_1h(self):
        self.assertEqual(_parse_period("1h"), timedelta(hours=1))

    def test_30d(self):
        self.assertEqual(_parse_period("30d"), timedelta(days=30))


class TestSummarizeGroup(unittest.TestCase):
    """Tests for summaries._summarize_group() — group summary lines."""

    def test_empty_returns_empty(self):
        self.assertEqual(_summarize_group([]), [])

    def test_returns_list(self):
        result = _summarize_group([{"content": "hello"}])
        self.assertIsInstance(result, list)

    def test_each_item_is_string(self):
        result = _summarize_group([{"content": "hello"}])
        self.assertIsInstance(result[0], str)

    def test_line_starts_with_dash(self):
        result = _summarize_group([{"content": "hello world"}])
        self.assertTrue(result[0].startswith("- "))

    def test_long_content_truncated_to_140(self):
        long_content = "x" * 200
        result = _summarize_group([{"content": long_content}])
        # Output should be truncated + "..."
        self.assertLessEqual(len(result[0]), 150)
        self.assertTrue(result[0].endswith("..."))

    def test_short_content_not_truncated(self):
        short = "hello world"
        result = _summarize_group([{"content": short}])
        self.assertIn(short, result[0])

    def test_max_10_rows_returned(self):
        rows = [{"content": f"item {i}"} for i in range(20)]
        result = _summarize_group(rows)
        self.assertLessEqual(len(result), 10)

    def test_missing_content_ok(self):
        result = _summarize_group([{}])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
