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
