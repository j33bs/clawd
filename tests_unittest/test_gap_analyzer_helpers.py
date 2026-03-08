"""Tests for workspace/research/gap_analyzer.py pure helpers.

Stdlib-only, no external deps. Loaded with a unique module name.

Covers:
- _normalize_topic
- _parse_topics_file
- _topic_counts
- analyze_gaps
- publish_gap_report
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = _ilu.spec_from_file_location(
    "gap_analyzer_real",
    str(REPO_ROOT / "workspace" / "research" / "gap_analyzer.py"),
)
ga = _ilu.module_from_spec(_spec)
sys.modules["gap_analyzer_real"] = ga
_spec.loader.exec_module(ga)


# ---------------------------------------------------------------------------
# _normalize_topic
# ---------------------------------------------------------------------------

class TestNormalizeTopic(unittest.TestCase):
    """Tests for _normalize_topic() — normalizes a topic label."""

    def test_lowercased(self):
        self.assertEqual(ga._normalize_topic("Machine Learning"), "machine_learning")

    def test_hyphens_to_underscores(self):
        self.assertEqual(ga._normalize_topic("deep-learning"), "deep_learning")

    def test_spaces_to_underscores(self):
        self.assertEqual(ga._normalize_topic("natural language"), "natural_language")

    def test_special_chars_removed(self):
        result = ga._normalize_topic("topic!")
        self.assertNotIn("!", result)

    def test_consecutive_underscores_collapsed(self):
        result = ga._normalize_topic("a--b")
        self.assertNotIn("__", result)

    def test_leading_trailing_underscores_stripped(self):
        result = ga._normalize_topic("_topic_")
        self.assertFalse(result.startswith("_"))
        self.assertFalse(result.endswith("_"))

    def test_empty_string_returns_empty(self):
        self.assertEqual(ga._normalize_topic(""), "")

    def test_returns_string(self):
        self.assertIsInstance(ga._normalize_topic("ai"), str)


# ---------------------------------------------------------------------------
# _parse_topics_file
# ---------------------------------------------------------------------------

class TestParseTopicsFile(unittest.TestCase):
    """Tests for _parse_topics_file() — parses markdown table for topics."""

    def test_missing_file_returns_empty(self):
        result = ga._parse_topics_file(Path("/nonexistent/topics.md"))
        self.assertEqual(result, [])

    def test_valid_markdown_table_row(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "topics.md"
            p.write_text("| **Machine Learning** | some col |\n", encoding="utf-8")
            result = ga._parse_topics_file(p)
            self.assertIn("machine_learning", result)

    def test_deduplicates_topics(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "topics.md"
            p.write_text(
                "| **NLP** | col |\n" * 3,
                encoding="utf-8",
            )
            result = ga._parse_topics_file(p)
            self.assertEqual(result.count("nlp"), 1)

    def test_non_matching_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "topics.md"
            p.write_text("just some text\n# header\n", encoding="utf-8")
            result = ga._parse_topics_file(p)
            self.assertEqual(result, [])

    def test_returns_list(self):
        result = ga._parse_topics_file(Path("/no/file"))
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# _topic_counts
# ---------------------------------------------------------------------------

class TestTopicCounts(unittest.TestCase):
    """Tests for _topic_counts() — counts topics from a JSONL papers file."""

    def test_missing_file_returns_zero(self):
        total, counts = ga._topic_counts(Path("/no/file.jsonl"))
        self.assertEqual(total, 0)
        self.assertEqual(counts, {})

    def test_valid_jsonl_counted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text(
                json.dumps({"topic": "NLP"}) + "\n"
                + json.dumps({"topic": "NLP"}) + "\n"
                + json.dumps({"topic": "CV"}) + "\n",
                encoding="utf-8",
            )
            total, counts = ga._topic_counts(p)
            self.assertEqual(total, 3)
            self.assertEqual(counts.get("nlp"), 2)
            self.assertEqual(counts.get("cv"), 1)

    def test_bad_json_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text("NOT JSON\n" + json.dumps({"topic": "AI"}) + "\n", encoding="utf-8")
            total, counts = ga._topic_counts(p)
            self.assertEqual(total, 1)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text("\n\n" + json.dumps({"topic": "RL"}) + "\n\n", encoding="utf-8")
            total, counts = ga._topic_counts(p)
            self.assertEqual(total, 1)

    def test_returns_tuple(self):
        total, counts = ga._topic_counts(Path("/no/file"))
        self.assertIsInstance(total, int)
        self.assertIsInstance(counts, dict)


# ---------------------------------------------------------------------------
# analyze_gaps
# ---------------------------------------------------------------------------

class TestAnalyzeGaps(unittest.TestCase):
    """Tests for analyze_gaps() — identifies low-coverage topics."""

    def test_returns_dict_with_expected_keys(self):
        with tempfile.TemporaryDirectory() as td:
            papers = Path(td) / "papers.jsonl"
            topics = Path(td) / "topics.md"
            papers.write_text("", encoding="utf-8")
            topics.write_text("", encoding="utf-8")
            result = ga.analyze_gaps(papers_path=papers, topics_file=topics)
            self.assertIn("top_gaps", result)
            self.assertIn("papers_total", result)

    def test_missing_topic_is_gap(self):
        with tempfile.TemporaryDirectory() as td:
            papers = Path(td) / "papers.jsonl"
            topics = Path(td) / "topics.md"
            papers.write_text("", encoding="utf-8")
            topics.write_text("| **NLP** | col |\n", encoding="utf-8")
            result = ga.analyze_gaps(papers_path=papers, topics_file=topics)
            gap_topics = [g["topic"] for g in result["top_gaps"]]
            self.assertIn("nlp", gap_topics)

    def test_covered_topic_not_in_gaps(self):
        with tempfile.TemporaryDirectory() as td:
            papers = Path(td) / "papers.jsonl"
            topics = Path(td) / "topics.md"
            # Write 2 distinct rows so count=2 > threshold=1
            papers.write_text(
                json.dumps({"topic": "NLP"}) + "\n" + json.dumps({"topic": "NLP"}) + "\n",
                encoding="utf-8",
            )
            topics.write_text("| **NLP** | col |\n", encoding="utf-8")
            # threshold=1 means count > 1 is covered (count=2 passes)
            result = ga.analyze_gaps(
                papers_path=papers, topics_file=topics, low_coverage_threshold=1
            )
            gap_topics = [g["topic"] for g in result["top_gaps"]]
            self.assertNotIn("nlp", gap_topics)

    def test_top_k_limits_results(self):
        with tempfile.TemporaryDirectory() as td:
            papers = Path(td) / "papers.jsonl"
            topics = Path(td) / "topics.md"
            papers.write_text("", encoding="utf-8")
            lines = "".join(f"| **Topic{i}** | col |\n" for i in range(10))
            topics.write_text(lines, encoding="utf-8")
            result = ga.analyze_gaps(papers_path=papers, topics_file=topics, top_k=3)
            self.assertLessEqual(len(result["top_gaps"]), 3)


# ---------------------------------------------------------------------------
# publish_gap_report
# ---------------------------------------------------------------------------

class TestPublishGapReport(unittest.TestCase):
    """Tests for publish_gap_report() — appends signed report to JSONL."""

    def _sample_report(self):
        return {
            "ts_utc": "2026-01-01T00:00:00Z",
            "type": "research_gap_report",
            "papers_total": 10,
            "topics_expected": 5,
            "topics_observed": 3,
            "top_gaps": [{"topic": "nlp", "count": 0, "status": "missing"}],
        }

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            result = ga.publish_gap_report(report=self._sample_report(), repo_root=Path(td))
            self.assertTrue(result["ok"])

    def test_appended_true_on_first_write(self):
        with tempfile.TemporaryDirectory() as td:
            result = ga.publish_gap_report(report=self._sample_report(), repo_root=Path(td))
            self.assertTrue(result["appended"])

    def test_duplicate_report_not_appended(self):
        with tempfile.TemporaryDirectory() as td:
            report = self._sample_report()
            ga.publish_gap_report(report=report, repo_root=Path(td))
            result = ga.publish_gap_report(report=report, repo_root=Path(td))
            self.assertFalse(result["appended"])

    def test_signature_added(self):
        with tempfile.TemporaryDirectory() as td:
            ga.publish_gap_report(report=self._sample_report(), repo_root=Path(td))
            kb = Path(td) / "workspace" / "knowledge_base" / "data" / "research_gap_reports.jsonl"
            row = json.loads(kb.read_text(encoding="utf-8").strip())
            self.assertIn("signature", row)
            self.assertEqual(len(row["signature"]), 64)

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            result = ga.publish_gap_report(report=self._sample_report(), repo_root=Path(td))
            self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
