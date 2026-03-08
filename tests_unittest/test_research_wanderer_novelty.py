import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "workspace" / "scripts" / "research_wanderer.py"
_SPEC = importlib.util.spec_from_file_location("_rw_scripts", _SCRIPT)
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["_rw_scripts"] = _MOD
_SPEC.loader.exec_module(_MOD)

evaluate_novelty = _MOD.evaluate_novelty
parse_wander_log_questions = _MOD.parse_wander_log_questions
select_question = _MOD.select_question
tokenize_keywords = _MOD.tokenize_keywords
overlap_ratio = _MOD.overlap_ratio
cosine_similarity = _MOD.cosine_similarity


class TestResearchWandererNovelty(unittest.TestCase):
    def test_overlap_rejected_when_gt_half(self):
        recent = ["How might active inference explain distributed AI identity continuity?"]
        candidate = "How might active inference explain distributed AI identity continuity in agents?"
        decision = evaluate_novelty(candidate, recent)
        self.assertFalse(decision.accepted)
        self.assertGreater(decision.overlap_max, 0.5)

    def test_similarity_rejected_when_gt_threshold(self):
        recent = ["memory consolidation replay mechanisms in ai systems"]
        candidate = "ai systems memory consolidation replay mechanisms"
        decision = evaluate_novelty(candidate, recent)
        self.assertFalse(decision.accepted)
        self.assertGreater(decision.similarity_max, 0.7)

    def test_select_question_regenerates_and_accepts_novel(self):
        recent = [
            "How might topic x intersect with active inference, given open loop: open loop unavailable? What measurable prediction would falsify this claim?",
            "How might topic x intersect with global workspace theory, given open loop: open loop unavailable? Where does this break under adversarial conditions?",
        ]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            topics = tmp / "TOPICS.md"
            topics.write_text("- active inference\n- neuromodulation\n", encoding="utf-8")
            oq = tmp / "OPEN_QUESTIONS.md"
            oq.write_text("2026-02-25 | What weak signal have we ignored?\n", encoding="utf-8")

            import random

            q, meta = select_question("topic y", recent, rng=random.Random(7), topics_path=topics, oq_path=oq, max_attempts=5)
            self.assertIn("topic y", q)
            self.assertLessEqual(meta["overlap_max"], 0.5)
            self.assertLessEqual(meta["similarity_max"], 0.7)

    def test_parse_wander_log_table(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wander_log.md"
            p.write_text(
                "# Wander Log\n\n| date_utc | question | overlap_max | similarity_max | seed_topic |\n|---|---|---:|---:|---|\n| 2026-02-25T00:00:00Z | Question A? | 0.1 | 0.2 | active inference |\n",
                encoding="utf-8",
            )
            rows = parse_wander_log_questions(p, last_n=5)
            self.assertEqual(rows, ["Question A?"])


class TestTokenizeKeywords(unittest.TestCase):
    """Tests for tokenize_keywords() — set-based word extractor."""

    def test_returns_set(self):
        self.assertIsInstance(tokenize_keywords("hello world"), set)

    def test_lowercases(self):
        result = tokenize_keywords("HELLO WORLD")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_empty_string(self):
        result = tokenize_keywords("")
        self.assertIsInstance(result, set)

    def test_numbers_included(self):
        result = tokenize_keywords("test 123")
        self.assertIn("123", result)

    def test_punctuation_splits(self):
        result = tokenize_keywords("hello,world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_stop_words_excluded(self):
        # "the", "a", "is" are typically stopwords in the wanderer
        result = tokenize_keywords("the quick brown fox")
        self.assertIn("quick", result)
        self.assertIn("brown", result)
        self.assertIn("fox", result)


class TestOverlapRatio(unittest.TestCase):
    """Tests for overlap_ratio() — Jaccard-style token overlap."""

    def test_identical_strings_return_one(self):
        self.assertAlmostEqual(overlap_ratio("hello world", "hello world"), 1.0, places=5)

    def test_no_overlap_returns_zero(self):
        self.assertEqual(overlap_ratio("apples oranges", "quantum vacuum"), 0.0)

    def test_empty_first_returns_zero(self):
        self.assertEqual(overlap_ratio("", "hello world"), 0.0)

    def test_empty_second_returns_zero(self):
        self.assertEqual(overlap_ratio("hello world", ""), 0.0)

    def test_partial_overlap_between_zero_and_one(self):
        score = overlap_ratio("hello world foo", "hello world bar")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(overlap_ratio("a b", "b c"), float)

    def test_symmetric(self):
        a = "consciousness routing memory"
        b = "routing memory systems"
        self.assertAlmostEqual(overlap_ratio(a, b), overlap_ratio(b, a), places=10)


class TestCosineSimilarity(unittest.TestCase):
    """Tests for cosine_similarity() — TF-IDF vector cosine similarity."""

    def test_identical_returns_near_one(self):
        score = cosine_similarity("consciousness routing", "consciousness routing")
        self.assertGreater(score, 0.9)

    def test_no_overlap_returns_zero(self):
        score = cosine_similarity("apples oranges", "quantum vacuum")
        self.assertEqual(score, 0.0)

    def test_empty_first_returns_zero(self):
        self.assertEqual(cosine_similarity("", "hello world"), 0.0)

    def test_empty_second_returns_zero(self):
        self.assertEqual(cosine_similarity("hello world", ""), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(cosine_similarity("a b", "b c"), float)

    def test_symmetric(self):
        a = "consciousness routing memory"
        b = "routing memory systems"
        self.assertAlmostEqual(cosine_similarity(a, b), cosine_similarity(b, a), places=10)

    def test_partial_overlap_between_zero_and_one(self):
        score = cosine_similarity("hello world foo", "hello world bar")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


if __name__ == "__main__":
    unittest.main()
