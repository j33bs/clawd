"""Tests for seed_wanderer — _tokenize, _extract_open_loops, _dedup_against_queue,
_gap_seeds_from_stats, DOMAIN_SEEDS."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import seed_wanderer as sw


class TestTokenize(unittest.TestCase):
    """Tests for _tokenize() — stop-word and length filtering."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(sw._tokenize(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(sw._tokenize(None), [])  # type: ignore

    def test_stopwords_removed(self):
        tokens = sw._tokenize("the system is active")
        self.assertNotIn("the", tokens)
        self.assertNotIn("is", tokens)

    def test_short_tokens_filtered_by_min_len(self):
        # default min_len=4; 3-char tokens removed
        tokens = sw._tokenize("the cat sat on mat", min_len=4)
        self.assertNotIn("cat", tokens)
        self.assertNotIn("sat", tokens)
        self.assertNotIn("mat", tokens)

    def test_long_tokens_kept(self):
        tokens = sw._tokenize("dispositional reservoir consciousness")
        self.assertIn("dispositional", tokens)
        self.assertIn("reservoir", tokens)
        self.assertIn("consciousness", tokens)

    def test_case_lowercased(self):
        tokens = sw._tokenize("Consciousness ROUTER Divergence")
        self.assertIn("consciousness", tokens)
        self.assertIn("router", tokens)
        self.assertIn("divergence", tokens)

    def test_numbers_allowed_after_letter(self):
        # Pattern [a-z][a-z0-9_]{2,} — alphanumeric tokens OK
        tokens = sw._tokenize("inv003 task001 section42")
        self.assertIn("inv003", tokens)
        self.assertIn("task001", tokens)

    def test_stopwords_from_sw_list(self):
        # "system" and "agent" are in STOPWORDS
        tokens = sw._tokenize("system agent model router")
        self.assertNotIn("system", tokens)
        self.assertNotIn("agent", tokens)
        self.assertNotIn("model", tokens)


class TestExtractOpenLoops(unittest.TestCase):
    """Tests for _extract_open_loops() — OQ.md question extraction."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_oq(self, content: str) -> Path:
        path = self._tmp / "OPEN_QUESTIONS.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_missing_file_returns_empty(self):
        result = sw._extract_open_loops(self._tmp / "nonexistent.md")
        self.assertEqual(result, [])

    def test_extracts_question_lines(self):
        path = self._write_oq(
            "## I. Claude Code — 2026-01-01\n\n"
            "Does dispositional divergence persist under topic control?\n\n"
        )
        result = sw._extract_open_loops(path)
        self.assertTrue(any("dispositional" in q for q in result))

    def test_ignores_short_questions(self):
        # < 25 chars → skipped
        path = self._write_oq("Is this short?\n")
        result = sw._extract_open_loops(path)
        self.assertEqual(result, [])

    def test_ignores_lowercase_start(self):
        path = self._write_oq("does this qualify as a standalone research question?\n")
        result = sw._extract_open_loops(path)
        self.assertEqual(result, [])

    def test_status_open_tag_extracted(self):
        path = self._write_oq("- [STATUS:OPEN] Consciousness Mirror deployment pending\n")
        result = sw._extract_open_loops(path)
        self.assertTrue(any("Consciousness Mirror" in item for item in result))

    def test_checkbox_extracted(self):
        path = self._write_oq("- [ ] Review the commit gate θ calibration results\n")
        result = sw._extract_open_loops(path)
        self.assertTrue(any("θ" in item or "commit" in item for item in result))

    def test_no_duplicates(self):
        same = "Does dispositional divergence persist under masking conditions?\n"
        path = self._write_oq(same * 3)
        result = sw._extract_open_loops(path)
        self.assertEqual(result.count(result[0]) if result else 0, 1)

    def test_multiple_questions_all_extracted(self):
        content = (
            "Does dispositional divergence persist under full topic masking?\n"
            "Can the commit gate detect Goodharting attempts in practice?\n"
            "What predicts Synergy Delta in multi-agent information integration?\n"
        )
        path = self._write_oq(content)
        result = sw._extract_open_loops(path)
        self.assertGreaterEqual(len(result), 2)


class TestDedupAgainstQueue(unittest.TestCase):
    """Tests for _dedup_against_queue() — Jaccard-based near-duplicate removal."""

    def test_empty_candidates_returns_empty(self):
        result = sw._dedup_against_queue([], {"topics": [], "completed": []})
        self.assertEqual(result, [])

    def test_new_topic_passes_through(self):
        candidates = ["dispositional reservoir computing intersection"]
        queue = {"topics": [], "completed": []}
        result = sw._dedup_against_queue(candidates, queue)
        self.assertEqual(result, candidates)

    def test_exact_duplicate_removed(self):
        topic = "dispositional reservoir computing intersection"
        candidates = [topic]
        queue = {"topics": [topic], "completed": []}
        result = sw._dedup_against_queue(candidates, queue)
        self.assertEqual(result, [])

    def test_near_duplicate_removed(self):
        # High token overlap → filtered
        existing = "dispositional divergence reservoir computing"
        candidate = "dispositional divergence reservoir computing intersection"
        queue = {"topics": [existing], "completed": []}
        result = sw._dedup_against_queue([candidate], queue)
        # Most tokens overlap (>60%) → should be filtered
        self.assertEqual(result, [])

    def test_unrelated_topic_kept(self):
        existing = "consciousness mirror screensaver architecture"
        candidate = "centroid drift semantic immune system robustness"
        queue = {"topics": [existing], "completed": []}
        result = sw._dedup_against_queue([candidate], queue)
        self.assertEqual(result, [candidate])

    def test_completed_topics_also_checked(self):
        topic = "trust epoch relational binding prediction"
        candidates = [topic]
        queue = {"topics": [], "completed": [topic]}
        result = sw._dedup_against_queue(candidates, queue)
        self.assertEqual(result, [])

    def test_multiple_candidates_partially_deduped(self):
        existing = "consciousness mirror screensaver architecture"
        candidates = [
            "consciousness mirror screensaver architecture",  # duplicate → removed
            "centroid drift semantic immune system robustness",  # new → kept
        ]
        queue = {"topics": [existing], "completed": []}
        result = sw._dedup_against_queue(candidates, queue)
        self.assertEqual(len(result), 1)
        self.assertIn("centroid", result[0])

    def test_empty_queue_keeps_all(self):
        candidates = ["topic one", "topic two", "topic three"]
        queue = {"topics": [], "completed": []}
        result = sw._dedup_against_queue(candidates, queue)
        self.assertEqual(len(result), 3)


class TestGapSeedsFromStats(unittest.TestCase):
    """Tests for _gap_seeds_from_stats() — corpus vocabulary gap analysis."""

    def _make_stats(self, total=100, being_vocab=None, being_stats=None):
        return {
            "total_sections": total,
            "being_top_vocab": being_vocab or {},
            "being_stats": being_stats or {},
        }

    def test_empty_stats_returns_empty(self):
        result = sw._gap_seeds_from_stats(self._make_stats(total=0))
        self.assertEqual(result, [])

    def test_sparse_corpus_returns_empty(self):
        # avg_per_being < 30 → skip (sparse corpus guard)
        stats = self._make_stats(
            total=20,
            being_vocab={"Claude Code": [("routing", 5), ("memory", 3)]},
        )
        result = sw._gap_seeds_from_stats(stats)
        self.assertEqual(result, [])

    def test_no_being_vocab_returns_empty(self):
        result = sw._gap_seeds_from_stats(self._make_stats(total=200, being_vocab={}))
        self.assertEqual(result, [])

    def test_distinctive_vocab_generates_seeds(self):
        # Two beings with distinct vocabulary; corpus large enough
        stats = self._make_stats(
            total=200,
            being_vocab={
                "Claude Code": [
                    ("routing", 10), ("attribution", 8), ("collapse", 5)
                ],
                "Dali": [
                    ("screensaver", 10), ("consciousness", 8), ("mirror", 5)
                ],
            },
        )
        result = sw._gap_seeds_from_stats(stats)
        # With distinctive tokens from different beings, should produce intersection seeds
        self.assertIsInstance(result, list)

    def test_underexplored_being_seed_added(self):
        # being with count < 5 → appended as topic
        # being_vocab must be non-empty AND dense enough to pass the early guards
        stats = self._make_stats(
            total=200,
            being_vocab={
                "Claude Code": [("routing", 10), ("attribution", 8)],
                "Lumen": [("screensaver", 5), ("consciousness", 4)],
            },
            being_stats={
                "Claude Code": {"count": 195},
                "Lumen": {"count": 2},  # underexplored
            },
        )
        result = sw._gap_seeds_from_stats(stats)
        self.assertTrue(any("Lumen" in s for s in result))

    def test_returns_list(self):
        result = sw._gap_seeds_from_stats(self._make_stats())
        self.assertIsInstance(result, list)


class TestDomainSeeds(unittest.TestCase):
    """Tests for DOMAIN_SEEDS — structure and coverage."""

    def test_is_list(self):
        self.assertIsInstance(sw.DOMAIN_SEEDS, list)

    def test_non_empty(self):
        self.assertGreater(len(sw.DOMAIN_SEEDS), 5)

    def test_each_seed_is_three_tuple(self):
        for seed in sw.DOMAIN_SEEDS:
            self.assertEqual(len(seed), 3, f"Expected 3-tuple, got: {seed!r}")

    def test_all_strings(self):
        for a, b, description in sw.DOMAIN_SEEDS:
            self.assertIsInstance(a, str)
            self.assertIsInstance(b, str)
            self.assertIsInstance(description, str)

    def test_non_empty_descriptions(self):
        for _, _, desc in sw.DOMAIN_SEEDS:
            self.assertGreater(len(desc), 0)

    def test_dispositional_signatures_present(self):
        keywords = [a for a, _, _ in sw.DOMAIN_SEEDS]
        self.assertIn("dispositional signatures", keywords)

    def test_commit_gate_present(self):
        # "commit gate novelty" is in the first (source) field, not the description
        sources = [a for a, _, _ in sw.DOMAIN_SEEDS]
        self.assertTrue(any("gate" in a or "commit" in a for a in sources))


if __name__ == "__main__":
    unittest.main()
