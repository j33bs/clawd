import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace" / "research"))

import research_ingest  # noqa: E402


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
