"""Tests for pure helpers in workspace/scripts/research_wanderer.py.

All stdlib — no network, no LLM calls, minimal file I/O (tempfile only).

Covers:
- iso_utc
- tokenize_keywords
- overlap_ratio
- cosine_similarity
- _redact_secretish_tokens
- _extract_date
- load_queue (missing file → default)
- load_findings (missing file → default)
- load_topics (from tempfile)
- evaluate_novelty
- parse_wander_log_questions (from tempfile)
"""
import importlib.util as _ilu
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

# Load the real research_wanderer.py explicitly to avoid the workspace/research/
# compatibility wrapper (which only re-exports a subset of functions) being picked
# up first when workspace/research/ appears earlier in sys.path.
_rw_spec = _ilu.spec_from_file_location(
    "research_wanderer_real",
    str(SCRIPTS_DIR / "research_wanderer.py"),
)
rw = _ilu.module_from_spec(_rw_spec)
sys.modules["research_wanderer_real"] = rw
_rw_spec.loader.exec_module(rw)


# ---------------------------------------------------------------------------
# iso_utc
# ---------------------------------------------------------------------------

class TestIsoUtc(unittest.TestCase):
    """Tests for iso_utc() — UTC ISO timestamp with Z suffix."""

    def test_returns_string(self):
        self.assertIsInstance(rw.iso_utc(), str)

    def test_ends_with_z(self):
        self.assertTrue(rw.iso_utc().endswith("Z"))

    def test_format_parseable(self):
        result = rw.iso_utc()
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")

    def test_no_microseconds(self):
        self.assertNotIn(".", rw.iso_utc())


# ---------------------------------------------------------------------------
# tokenize_keywords
# ---------------------------------------------------------------------------

class TestTokenizeKeywords(unittest.TestCase):
    """Tests for tokenize_keywords() — keyword extraction with stopword filter."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(rw.tokenize_keywords(""), set())

    def test_basic_tokens_extracted(self):
        result = rw.tokenize_keywords("active inference agent")
        self.assertIn("active", result)
        self.assertIn("inference", result)
        self.assertIn("agent", result)

    def test_stopwords_excluded(self):
        result = rw.tokenize_keywords("what the world does mean")
        self.assertNotIn("what", result)
        self.assertNotIn("the", result)
        self.assertNotIn("does", result)
        self.assertNotIn("mean", result)

    def test_short_words_excluded(self):
        # tokens shorter than 3 chars filtered
        result = rw.tokenize_keywords("AI in ml go")
        self.assertNotIn("ai", result)
        self.assertNotIn("in", result)
        self.assertNotIn("ml", result)
        self.assertNotIn("go", result)

    def test_returns_set(self):
        self.assertIsInstance(rw.tokenize_keywords("hello world"), set)

    def test_case_lowercased(self):
        result = rw.tokenize_keywords("Active Inference")
        self.assertIn("active", result)
        self.assertIn("inference", result)
        self.assertNotIn("Active", result)


# ---------------------------------------------------------------------------
# overlap_ratio
# ---------------------------------------------------------------------------

class TestOverlapRatio(unittest.TestCase):
    """Tests for overlap_ratio() — Jaccard-like overlap between two texts."""

    def test_identical_strings_near_one(self):
        result = rw.overlap_ratio("active inference model", "active inference model")
        self.assertAlmostEqual(result, 1.0)

    def test_disjoint_strings_zero(self):
        result = rw.overlap_ratio("alpha beta gamma", "delta epsilon zeta")
        self.assertAlmostEqual(result, 0.0)

    def test_partial_overlap(self):
        # shared: "inference"
        result = rw.overlap_ratio("active inference", "inference machine")
        self.assertGreater(result, 0.0)
        self.assertLess(result, 1.0)

    def test_empty_both_zero(self):
        self.assertAlmostEqual(rw.overlap_ratio("", ""), 0.0)

    def test_returns_float(self):
        self.assertIsInstance(rw.overlap_ratio("hello world", "hello there"), float)

    def test_result_bounded(self):
        result = rw.overlap_ratio("foo bar baz", "bar baz qux")
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity(unittest.TestCase):
    """Tests for cosine_similarity() — keyword-based cosine between two texts."""

    def test_identical_strings_one(self):
        result = rw.cosine_similarity("active inference", "active inference")
        self.assertAlmostEqual(result, 1.0)

    def test_disjoint_strings_zero(self):
        result = rw.cosine_similarity("alpha beta gamma", "delta epsilon zeta")
        self.assertAlmostEqual(result, 0.0)

    def test_empty_a_returns_zero(self):
        self.assertAlmostEqual(rw.cosine_similarity("", "hello world"), 0.0)

    def test_empty_b_returns_zero(self):
        self.assertAlmostEqual(rw.cosine_similarity("hello world", ""), 0.0)

    def test_partial_overlap_between_zero_and_one(self):
        result = rw.cosine_similarity("active inference agent", "inference neural model")
        self.assertGreater(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_returns_float(self):
        self.assertIsInstance(rw.cosine_similarity("a b c", "b c d"), float)


# ---------------------------------------------------------------------------
# _redact_secretish_tokens
# ---------------------------------------------------------------------------

class TestRedactSecretishTokens(unittest.TestCase):
    """Tests for _redact_secretish_tokens() — redacts long opaque tokens."""

    def test_long_token_redacted(self):
        text = "token=abcdefghijklmnopqrstuvwxyz1234567890"
        result = rw._redact_secretish_tokens(text)
        self.assertIn("[REDACTED_TOKEN]", result)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz1234567890", result)

    def test_short_token_not_redacted(self):
        # Only tokens ≥ 20 chars are redacted
        result = rw._redact_secretish_tokens("hello world shortok")
        self.assertNotIn("[REDACTED_TOKEN]", result)

    def test_empty_string_returns_empty(self):
        self.assertEqual(rw._redact_secretish_tokens(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(rw._redact_secretish_tokens(None), "")

    def test_normal_text_unchanged(self):
        text = "research about active inference"
        result = rw._redact_secretish_tokens(text)
        self.assertIn("research", result)
        self.assertIn("inference", result)

    def test_returns_string(self):
        self.assertIsInstance(rw._redact_secretish_tokens("text"), str)


# ---------------------------------------------------------------------------
# _extract_date
# ---------------------------------------------------------------------------

class TestExtractDate(unittest.TestCase):
    """Tests for _extract_date() — extract date from a line of text."""

    def test_valid_date_extracted(self):
        result = rw._extract_date("on 2026-03-07 something happened")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 7)

    def test_no_date_returns_none(self):
        result = rw._extract_date("no date in this line")
        self.assertIsNone(result)

    def test_returns_utc_datetime(self):
        result = rw._extract_date("2026-01-15 data")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_invalid_date_returns_none(self):
        # "20ab-cd-ef" won't match the pattern, 20\d\d-\d\d-\d\d
        result = rw._extract_date("date: 20ab-cd-ef blah")
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        self.assertIsNone(rw._extract_date(""))


# ---------------------------------------------------------------------------
# load_queue (missing file → default structure)
# ---------------------------------------------------------------------------

class TestLoadQueue(unittest.TestCase):
    """Tests for load_queue() — JSON queue loader with defaults."""

    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonexistent.json"
            result = rw.load_queue(path=p)
            self.assertIn("topics", result)
            self.assertIn("completed", result)
            self.assertIn("last_wander", result)

    def test_default_topics_populated(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonexistent.json"
            result = rw.load_queue(path=p)
            self.assertIsInstance(result["topics"], list)
            self.assertGreater(len(result["topics"]), 0)

    def test_existing_file_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "queue.json"
            import json
            p.write_text(json.dumps({"topics": ["custom"], "completed": [], "last_wander": None}), encoding="utf-8")
            result = rw.load_queue(path=p)
            self.assertEqual(result["topics"], ["custom"])

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            result = rw.load_queue(path=Path(td) / "missing.json")
            self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# load_findings (missing file → default structure)
# ---------------------------------------------------------------------------

class TestLoadFindings(unittest.TestCase):
    """Tests for load_findings() — JSON findings loader with defaults."""

    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonexistent.json"
            result = rw.load_findings(path=p)
            self.assertIn("findings", result)
            self.assertIn("questions_generated", result)

    def test_default_findings_empty_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonexistent.json"
            result = rw.load_findings(path=p)
            self.assertEqual(result["findings"], [])

    def test_existing_file_loaded(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "findings.json"
            p.write_text(json.dumps({"findings": ["f1"], "questions_generated": ["q1"]}), encoding="utf-8")
            result = rw.load_findings(path=p)
            self.assertEqual(result["findings"], ["f1"])

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            result = rw.load_findings(path=Path(td) / "missing.json")
            self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# load_topics (tempfile)
# ---------------------------------------------------------------------------

class TestLoadTopics(unittest.TestCase):
    """Tests for load_topics() — markdown topic list loader."""

    def test_parses_dash_bullets(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("# Topics\n\n- active inference\n- global workspace\n", encoding="utf-8")
            result = rw.load_topics(path=p)
            self.assertIn("active inference", result)
            self.assertIn("global workspace", result)

    def test_parses_asterisk_bullets(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("* topic one\n* topic two\n", encoding="utf-8")
            result = rw.load_topics(path=p)
            self.assertIn("topic one", result)
            self.assertIn("topic two", result)

    def test_missing_file_creates_default(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "subdir" / "TOPICS.md"
            result = rw.load_topics(path=p)
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)

    def test_non_bullet_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("# Header\nplain text\n- valid topic\n", encoding="utf-8")
            result = rw.load_topics(path=p)
            self.assertEqual(result, ["valid topic"])

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("- alpha\n", encoding="utf-8")
            self.assertIsInstance(rw.load_topics(path=p), list)


# ---------------------------------------------------------------------------
# evaluate_novelty
# ---------------------------------------------------------------------------

class TestEvaluateNovelty(unittest.TestCase):
    """Tests for evaluate_novelty() — novelty scoring against recent questions."""

    def test_novel_question_accepted(self):
        recent = ["What is the nature of consciousness?"]
        candidate = "How does predictive processing explain dreaming?"
        result = rw.evaluate_novelty(candidate, recent)
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason, "accepted")

    def test_duplicate_question_rejected(self):
        q = "What measurable prediction would falsify this claim about active inference?"
        result = rw.evaluate_novelty(q, [q])
        self.assertFalse(result.accepted)

    def test_empty_recent_accepted(self):
        result = rw.evaluate_novelty("What is the role of sleep in memory consolidation?", [])
        self.assertTrue(result.accepted)

    def test_returns_novelty_decision(self):
        result = rw.evaluate_novelty("Any question?", [])
        self.assertIsInstance(result, rw.NoveltyDecision)
        self.assertIsInstance(result.accepted, bool)
        self.assertIsInstance(result.overlap_max, float)
        self.assertIsInstance(result.similarity_max, float)
        self.assertIsInstance(result.reason, str)

    def test_high_overlap_rejected(self):
        # Same tokens → overlap > 0.5 → rejected
        q = "active inference neural processing model prediction"
        result = rw.evaluate_novelty(q, [q])
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "rejected_overlap")


# ---------------------------------------------------------------------------
# parse_wander_log_questions
# ---------------------------------------------------------------------------

class TestParseWanderLogQuestions(unittest.TestCase):
    """Tests for parse_wander_log_questions() — parse MD table from wander log."""

    def test_missing_file_returns_empty(self):
        result = rw.parse_wander_log_questions(path=Path("/nonexistent/log.md"))
        self.assertEqual(result, [])

    def test_valid_table_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            p.write_text(
                "| date_utc | question | overlap | sim | seed |\n"
                "|---|---|---|---|---|\n"
                "| 2026-03-07T10:00:00Z | What is active inference? | 0.1 | 0.2 | topic1 |\n",
                encoding="utf-8",
            )
            result = rw.parse_wander_log_questions(path=p)
            self.assertEqual(len(result), 1)
            self.assertIn("What is active inference?", result)

    def test_returns_list(self):
        result = rw.parse_wander_log_questions(path=Path("/no/file.md"))
        self.assertIsInstance(result, list)

    def test_last_n_limits(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "log.md"
            rows = "\n".join(
                f"| 2026-03-0{i+1}T00:00:00Z | Question {i} | 0.0 | 0.0 | topic |"
                for i in range(5)
            )
            p.write_text(
                "| date_utc | question | overlap | sim | seed |\n|---|---|---|---|---|\n" + rows,
                encoding="utf-8",
            )
            result = rw.parse_wander_log_questions(path=p, last_n=3)
            self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
