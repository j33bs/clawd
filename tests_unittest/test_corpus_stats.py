"""Tests for corpus_stats — _tokenize, _jaccard, _top_n, _parse_sections_fallback,
and compute_stats."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import corpus_stats as cs


class TestTokenize(unittest.TestCase):
    """Tests for _tokenize() — token extraction with stopword filtering."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(cs._tokenize(""), [])

    def test_none_like_returns_empty(self):
        self.assertEqual(cs._tokenize(None), [])  # type: ignore

    def test_stopwords_removed(self):
        tokens = cs._tokenize("the memory system is")
        self.assertNotIn("the", tokens)
        self.assertNotIn("is", tokens)

    def test_short_words_filtered(self):
        # Tokens shorter than 3 chars (regex: [a-z][a-z0-9_]{2,}) filtered
        tokens = cs._tokenize("an ok go go")
        self.assertNotIn("an", tokens)
        self.assertNotIn("ok", tokens)
        self.assertNotIn("go", tokens)

    def test_meaningful_words_kept(self):
        tokens = cs._tokenize("memory routing consciousness attribution")
        self.assertIn("memory", tokens)
        self.assertIn("routing", tokens)
        self.assertIn("consciousness", tokens)
        self.assertIn("attribution", tokens)

    def test_case_normalized(self):
        tokens = cs._tokenize("Memory ROUTING Consciousness")
        self.assertIn("memory", tokens)
        self.assertIn("routing", tokens)

    def test_duplicate_tokens_preserved(self):
        tokens = cs._tokenize("memory memory routing memory")
        self.assertEqual(tokens.count("memory"), 3)

    def test_mixed_content(self):
        tokens = cs._tokenize("The routing system tracks memory attribution paths")
        self.assertIn("routing", tokens)
        self.assertIn("system", tokens)
        self.assertIn("memory", tokens)
        self.assertIn("attribution", tokens)
        self.assertNotIn("the", tokens)


class TestJaccard(unittest.TestCase):
    """Tests for _jaccard() — set similarity score."""

    def test_identical_sets_return_one(self):
        a = {"memory", "routing", "system"}
        self.assertAlmostEqual(cs._jaccard(a, a), 1.0)

    def test_empty_both_returns_one(self):
        self.assertAlmostEqual(cs._jaccard(set(), set()), 1.0)

    def test_disjoint_sets_return_zero(self):
        a = {"alpha", "beta"}
        b = {"gamma", "delta"}
        self.assertAlmostEqual(cs._jaccard(a, b), 0.0)

    def test_partial_overlap(self):
        a = {"alpha", "beta", "gamma"}
        b = {"beta", "gamma", "delta"}
        # intersection=2, union=4 → 0.5
        self.assertAlmostEqual(cs._jaccard(a, b), 0.5)

    def test_one_empty_returns_zero(self):
        self.assertAlmostEqual(cs._jaccard({"x"}, set()), 0.0)

    def test_symmetry(self):
        a = {"x", "y", "z"}
        b = {"y", "z", "w"}
        self.assertAlmostEqual(cs._jaccard(a, b), cs._jaccard(b, a))

    def test_subset_jaccard(self):
        # b is subset of a: |a|=4, |b|=2, |a∩b|=2, |a∪b|=4 → 0.5
        a = {"a", "b", "c", "d"}
        b = {"a", "b"}
        self.assertAlmostEqual(cs._jaccard(a, b), 0.5)


class TestTopN(unittest.TestCase):
    """Tests for _top_n() — top-N token Counter."""

    def test_empty_returns_empty(self):
        result = cs._top_n([])
        self.assertEqual(result, [])

    def test_returns_most_common(self):
        tokens = ["memory"] * 5 + ["routing"] * 3 + ["attribution"] * 1
        result = cs._top_n(tokens, n=2)
        self.assertEqual(result[0][0], "memory")
        self.assertEqual(result[0][1], 5)
        self.assertEqual(result[1][0], "routing")
        self.assertEqual(result[1][1], 3)

    def test_n_limits_output(self):
        tokens = ["a_word"] * 3 + ["b_word"] * 2 + ["c_word"] * 1
        result = cs._top_n(tokens, n=2)
        self.assertEqual(len(result), 2)

    def test_default_n_100(self):
        tokens = [f"word_{i}" for i in range(50)]  # 50 unique words
        result = cs._top_n(tokens)
        self.assertEqual(len(result), 50)  # fewer than 100 unique words


class TestParseSectionsFallback(unittest.TestCase):
    """Tests for _parse_sections_fallback() — OPEN_QUESTIONS.md parsing."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, content: str) -> Path:
        path = self._tmp / "OPEN_QUESTIONS.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_missing_file_returns_empty(self):
        result = cs._parse_sections_fallback(self._tmp / "nonexistent.md")
        self.assertEqual(result, [])

    def test_section_number_parsed(self):
        path = self._write("## I. Claude Code — 2026-01-01\n\nBody text.\n")
        result = cs._parse_sections_fallback(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["canonical_section_number"], 1)

    def test_author_extracted(self):
        path = self._write("## X. Claude Code — 2026-01-01\n\nContent.\n")
        result = cs._parse_sections_fallback(path)
        self.assertIn("Claude Code", result[0]["authors"])

    def test_c_lawd_author_extracted(self):
        path = self._write("## V. c_lawd — 2026-02-01\n\nContent.\n")
        result = cs._parse_sections_fallback(path)
        self.assertIn("c_lawd", result[0]["authors"])

    def test_date_extracted(self):
        path = self._write("## III. Dali — 2026-03-08\n\nContent.\n")
        result = cs._parse_sections_fallback(path)
        self.assertEqual(result[0]["created_at"], "2026-03-08")

    def test_exec_tag_detected(self):
        path = self._write(
            "## II. Claude Code — 2026-01-01\n\nContent with [EXEC:MICRO] tag.\n"
        )
        result = cs._parse_sections_fallback(path)
        self.assertIn("MICRO", result[0]["exec_tags"])

    def test_multiple_sections_parsed(self):
        content = (
            "## I. Claude Code — 2026-01-01\n\nFirst section.\n"
            "## II. Dali — 2026-01-02\n\nSecond section.\n"
        )
        path = self._write(content)
        result = cs._parse_sections_fallback(path)
        self.assertEqual(len(result), 2)

    def test_body_captured(self):
        path = self._write(
            "## IV. Grok — 2026-01-01\n\nThis is the body content.\n"
        )
        result = cs._parse_sections_fallback(path)
        self.assertIn("This is the body content.", result[0]["body"])

    def test_no_known_author_returns_empty_list(self):
        path = self._write("## I. Unknown Person — 2026-01-01\n\nContent.\n")
        result = cs._parse_sections_fallback(path)
        self.assertEqual(result[0]["authors"], [])

    def test_roman_numeral_xlii_42(self):
        path = self._write("## XLII. c_lawd — 2026-01-01\n\nContent.\n")
        result = cs._parse_sections_fallback(path)
        self.assertEqual(result[0]["canonical_section_number"], 42)


class TestComputeStats(unittest.TestCase):
    """Tests for compute_stats() — aggregate metrics."""

    def _make_section(self, number: int, author: str, body: str = "content") -> dict:
        return {
            "canonical_section_number": number,
            "authors": [author],
            "created_at": "2026-01-01",
            "body": body,
            "exec_tags": [],
            "status_tags": [],
            "response_to": [],
            "trust_epoch": "",
        }

    def test_empty_sections_returns_zero_total(self):
        result = cs.compute_stats([])
        self.assertEqual(result["total_sections"], 0)

    def test_total_sections_counted(self):
        sections = [self._make_section(i, "Claude Code") for i in range(5)]
        result = cs.compute_stats(sections)
        self.assertEqual(result["total_sections"], 5)

    def test_since_filter_applied(self):
        sections = [self._make_section(i, "Claude Code") for i in range(1, 11)]
        result = cs.compute_stats(sections, since=5)
        self.assertEqual(result["total_sections"], 6)  # 5,6,7,8,9,10

    def test_per_being_counts(self):
        sections = (
            [self._make_section(i, "Claude Code") for i in range(3)]
            + [self._make_section(i + 10, "Dali") for i in range(2)]
        )
        result = cs.compute_stats(sections)
        beings = result["being_stats"]
        self.assertEqual(beings["Claude Code"]["count"], 3)
        self.assertEqual(beings["Dali"]["count"], 2)

    def test_unknown_author_counted(self):
        sections = [{"canonical_section_number": 1, "authors": [], "created_at": "",
                     "body": "", "exec_tags": [], "status_tags": [], "response_to": [], "trust_epoch": ""}]
        result = cs.compute_stats(sections)
        self.assertIn("[unknown]", result["being_stats"])

    def test_exec_tag_distribution(self):
        s1 = self._make_section(1, "Claude Code", "tag [EXEC:MICRO] here")
        s1["exec_tags"] = ["MICRO"]
        s2 = self._make_section(2, "Dali", "tag [EXEC:GOV] here")
        s2["exec_tags"] = ["GOV"]
        result = cs.compute_stats([s1, s2])
        self.assertEqual(result["exec_tag_distribution"].get("MICRO"), 1)
        self.assertEqual(result["exec_tag_distribution"].get("GOV"), 1)


if __name__ == "__main__":
    unittest.main()
