import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "research") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "research"))

import gap_analyzer  # noqa: E402
import research_ingest  # noqa: E402

from gap_analyzer import _normalize_topic, _parse_topics_file, _topic_counts, _utc_now  # noqa: E402


class TestUtcNow(unittest.TestCase):
    """Tests for gap_analyzer._utc_now() — ISO timestamp helper."""

    def test_returns_string(self):
        self.assertIsInstance(_utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(_utc_now().endswith("Z"))

    def test_contains_t_separator(self):
        self.assertIn("T", _utc_now())

    def test_no_plus00(self):
        self.assertNotIn("+00:00", _utc_now())


class TestNormalizeTopic(unittest.TestCase):
    """Tests for gap_analyzer._normalize_topic() — slug normalization."""

    def test_lowercases(self):
        self.assertEqual(_normalize_topic("Memory"), "memory")

    def test_spaces_become_underscores(self):
        self.assertEqual(_normalize_topic("active inference"), "active_inference")

    def test_hyphens_become_underscores(self):
        self.assertEqual(_normalize_topic("cross-timescale"), "cross_timescale")

    def test_special_chars_removed(self):
        self.assertEqual(_normalize_topic("foo!bar@baz"), "foobarbaz")

    def test_multiple_underscores_collapsed(self):
        result = _normalize_topic("a  b")  # two spaces → two underscores → collapsed
        self.assertNotIn("__", result)

    def test_leading_trailing_underscores_stripped(self):
        result = _normalize_topic("_memory_")
        self.assertFalse(result.startswith("_"))
        self.assertFalse(result.endswith("_"))

    def test_empty_returns_empty(self):
        self.assertEqual(_normalize_topic(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_topic(None), "")  # type: ignore[arg-type]

    def test_returns_string(self):
        self.assertIsInstance(_normalize_topic("test"), str)


class TestParseTopicsFile(unittest.TestCase):
    """Tests for gap_analyzer._parse_topics_file() — markdown table parser."""

    def test_missing_file_returns_empty(self):
        result = _parse_topics_file(Path("/nonexistent/path/TOPICS.md"))
        self.assertEqual(result, [])

    def test_extracts_table_topics(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("| **memory** |\n| **arousal** |\n", encoding="utf-8")
            result = _parse_topics_file(p)
            self.assertIn("memory", result)
            self.assertIn("arousal", result)

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("| **memory** |\n| **memory** |\n", encoding="utf-8")
            result = _parse_topics_file(p)
            self.assertEqual(result.count("memory"), 1)

    def test_non_table_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("# heading\n| **memory** |\nsome text\n", encoding="utf-8")
            result = _parse_topics_file(p)
            self.assertEqual(result, ["memory"])

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("| **memory** |\n", encoding="utf-8")
            result = _parse_topics_file(p)
            self.assertIsInstance(result, list)


class TestTopicCounts(unittest.TestCase):
    """Tests for gap_analyzer._topic_counts() — JSONL topic frequency counter."""

    def test_missing_file_returns_zeros(self):
        total, counts = _topic_counts(Path("/nonexistent/papers.jsonl"))
        self.assertEqual(total, 0)
        self.assertEqual(counts, {})

    def test_counts_topics(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text(
                json.dumps({"topic": "memory"}) + "\n" +
                json.dumps({"topic": "memory"}) + "\n" +
                json.dumps({"topic": "arousal"}) + "\n",
                encoding="utf-8",
            )
            total, counts = _topic_counts(p)
            self.assertEqual(total, 3)
            self.assertEqual(counts["memory"], 2)
            self.assertEqual(counts["arousal"], 1)

    def test_invalid_json_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text(
                "not json\n" + json.dumps({"topic": "memory"}) + "\n",
                encoding="utf-8",
            )
            total, counts = _topic_counts(p)
            self.assertEqual(total, 1)

    def test_empty_file_returns_zeros(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text("", encoding="utf-8")
            total, counts = _topic_counts(p)
            self.assertEqual(total, 0)
            self.assertEqual(counts, {})

    def test_returns_int_and_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "papers.jsonl"
            p.write_text(json.dumps({"topic": "x"}) + "\n", encoding="utf-8")
            total, counts = _topic_counts(p)
            self.assertIsInstance(total, int)
            self.assertIsInstance(counts, dict)


class TestResearchGapAnalyzerBridge(unittest.TestCase):
    def test_analyze_and_publish_gap_report_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            papers = root / "papers.jsonl"
            topics = root / "TOPICS.md"
            papers.write_text(
                "\n".join(
                    [
                        json.dumps({"topic": "memory"}),
                        json.dumps({"topic": "memory"}),
                        json.dumps({"topic": "arousal"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            topics.write_text(
                "| **memory** |\n| **arousal** |\n| **novelty** |\n",
                encoding="utf-8",
            )

            report = gap_analyzer.analyze_gaps(papers_path=papers, topics_file=topics, low_coverage_threshold=1, top_k=5)
            self.assertEqual(report["type"], "research_gap_report")
            self.assertTrue(any(item["topic"] == "novelty" for item in report["top_gaps"]))

            first = gap_analyzer.publish_gap_report(report=report, repo_root=root)
            second = gap_analyzer.publish_gap_report(report=report, repo_root=root)
            self.assertTrue(first["appended"])
            self.assertFalse(second["appended"])

    def test_research_ingest_bridge_writes_kb_gap_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            papers = root / "papers.jsonl"
            topics = root / "TOPICS.md"
            papers.write_text(json.dumps({"topic": "memory"}) + "\n", encoding="utf-8")
            topics.write_text("| **memory** |\n| **novelty** |\n", encoding="utf-8")

            with patch.object(research_ingest, "PAPERS_FILE", papers):
                with patch.object(research_ingest, "__file__", str(root / "workspace" / "research" / "research_ingest.py")):
                    result = research_ingest._run_gap_bridge(topics_file=topics)

            self.assertTrue(result["ok"])
            kb_report = root / "workspace" / "knowledge_base" / "data" / "research_gap_reports.jsonl"
            self.assertTrue(kb_report.exists())


if __name__ == "__main__":
    unittest.main()
