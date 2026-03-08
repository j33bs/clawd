import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace" / "research"))

import research_ingest  # noqa: E402

from research_ingest import compute_hash, extract_text_from_html, normalize_topic, parse_topics_file  # noqa: E402


class TestComputeHash(unittest.TestCase):
    """Tests for research_ingest.compute_hash() — SHA-256 hex[:12]."""

    def test_returns_string(self):
        self.assertIsInstance(compute_hash("hello"), str)

    def test_length_is_12(self):
        self.assertEqual(len(compute_hash("hello")), 12)

    def test_deterministic(self):
        self.assertEqual(compute_hash("hello"), compute_hash("hello"))

    def test_different_inputs_different_hashes(self):
        self.assertNotEqual(compute_hash("a"), compute_hash("b"))

    def test_empty_string(self):
        result = compute_hash("")
        self.assertEqual(len(result), 12)

    def test_hex_chars_only(self):
        result = compute_hash("test content")
        self.assertTrue(all(c in "0123456789abcdef" for c in result))


class TestExtractTextFromHtml(unittest.TestCase):
    """Tests for research_ingest.extract_text_from_html() — HTML stripper."""

    def test_plain_text_unchanged(self):
        result = extract_text_from_html("hello world")
        self.assertIn("hello world", result)

    def test_script_tags_removed(self):
        html = "<script>alert('xss')</script>hello"
        result = extract_text_from_html(html)
        self.assertNotIn("alert", result)
        self.assertIn("hello", result)

    def test_style_tags_removed(self):
        html = "<style>body{color:red}</style>hello"
        result = extract_text_from_html(html)
        self.assertNotIn("color", result)
        self.assertIn("hello", result)

    def test_html_tags_stripped(self):
        html = "<p>hello <b>world</b></p>"
        result = extract_text_from_html(html)
        self.assertIn("hello", result)
        self.assertIn("world", result)
        self.assertNotIn("<", result)

    def test_html_entities_decoded(self):
        result = extract_text_from_html("&amp; &lt; &gt;")
        self.assertIn("&", result)
        self.assertIn("<", result)
        self.assertIn(">", result)

    def test_returns_string(self):
        self.assertIsInstance(extract_text_from_html("<p>hi</p>"), str)

    def test_empty_string(self):
        result = extract_text_from_html("")
        self.assertIsInstance(result, str)


class TestNormalizeTopic(unittest.TestCase):
    """Tests for research_ingest.normalize_topic() — slug normalization."""

    def test_lowercases(self):
        self.assertEqual(normalize_topic("Memory"), "memory")

    def test_spaces_become_underscores(self):
        self.assertEqual(normalize_topic("active inference"), "active_inference")

    def test_hyphens_become_underscores(self):
        self.assertEqual(normalize_topic("cross-timescale"), "cross_timescale")

    def test_special_chars_removed(self):
        self.assertEqual(normalize_topic("foo!bar"), "foobar")

    def test_multiple_underscores_collapsed(self):
        result = normalize_topic("a  b")
        self.assertNotIn("__", result)

    def test_returns_string(self):
        self.assertIsInstance(normalize_topic("test"), str)


class TestParseTopicsFileIngest(unittest.TestCase):
    """Tests for research_ingest.parse_topics_file() — Markdown topic parser."""

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            parse_topics_file(Path("/nonexistent/TOPICS.md"))

    def test_table_format_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("| **memory** | desc |\n| **arousal** |\n", encoding="utf-8")
            result = parse_topics_file(p)
            self.assertIn("memory", result)
            self.assertIn("arousal", result)

    def test_heading_format_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("#### Active Inference\n", encoding="utf-8")
            result = parse_topics_file(p)
            self.assertIn("active_inference", result)

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("| **memory** |\n| **memory** |\n", encoding="utf-8")
            result = parse_topics_file(p)
            self.assertEqual(result.count("memory"), 1)

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TOPICS.md"
            p.write_text("| **memory** |\n", encoding="utf-8")
            self.assertIsInstance(parse_topics_file(p), list)


class TestResearchIngest(unittest.TestCase):
    def test_parse_topics_file_extracts_framework_topics(self):
        with tempfile.TemporaryDirectory() as td:
            topics_md = Path(td) / "TOPICS.md"
            topics_md.write_text(
                """
| **temporality** | desc |
| **arousal** | desc |
| **cross_timescale** | desc |
| **collapse** | desc |
| **repairable** | desc |
""",
                encoding="utf-8",
            )
            topics = research_ingest.parse_topics_file(topics_md)
            self.assertEqual(
                topics,
                ["temporality", "arousal", "cross_timescale", "collapse", "repairable"],
            )

    @patch("research_ingest.probe_arxiv_connectivity", return_value={"ok": True, "status": 200})
    def test_ingest_topics_dry_run_writes_status_artifact(self, _mock_probe):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            topics_md = root / "TOPICS.md"
            out_dir = root / "reports"
            topics_md.write_text("| **temporality** | desc |\n", encoding="utf-8")

            code, status = research_ingest.ingest_topics(
                topics_file=topics_md,
                out_dir=out_dir,
                dry_run=True,
                max_results=1,
            )
            self.assertEqual(code, 0)
            self.assertEqual(status["topics_count"], 1)
            self.assertEqual(status["docs_ingested"], 0)

            status_path = out_dir / "ingest_status.json"
            self.assertTrue(status_path.exists())
            persisted = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertTrue(persisted["dry_run"])

    @patch("research_ingest.fetch_arxiv_entries")
    @patch("research_ingest.probe_arxiv_connectivity", return_value={"ok": True, "status": 200})
    def test_ingest_topics_persists_entries(self, _mock_probe, mock_fetch):
        mock_fetch.return_value = [
            {
                "entry_id": "http://arxiv.org/abs/1234.5678",
                "title": "Temporal Hierarchies for Agents",
                "summary": "A concise abstract.",
                "updated": "2026-02-18T00:00:00Z",
                "url": "http://arxiv.org/abs/1234.5678",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            topics_md = root / "TOPICS.md"
            out_dir = root / "reports"
            papers_file = root / "papers.jsonl"
            papers_file.write_text("", encoding="utf-8")
            topics_md.write_text("| **cross_timescale** | desc |\n", encoding="utf-8")

            with patch.object(research_ingest, "PAPERS_FILE", papers_file):
                code, status = research_ingest.ingest_topics(
                    topics_file=topics_md,
                    out_dir=out_dir,
                    dry_run=False,
                    max_results=1,
                )

            self.assertEqual(code, 0)
            self.assertEqual(status["docs_ingested"], 1)
            lines = [ln for ln in papers_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            stored = json.loads(lines[0])
            self.assertEqual(stored["topic"], "cross_timescale")


if __name__ == "__main__":
    unittest.main()
