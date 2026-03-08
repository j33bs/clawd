"""Tests for workspace/scripts/telegram_analysis.py pure helpers.

Covers (no network, no sklearn):
- load_rows
- analysis_enabled
- run_sentiment
- run_alignment_patterns
- run_relationship_growth
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from telegram_analysis import (  # noqa: E402
    analysis_enabled,
    load_rows,
    run_alignment_patterns,
    run_relationship_growth,
    run_sentiment,
)


# ---------------------------------------------------------------------------
# load_rows
# ---------------------------------------------------------------------------

class TestLoadRows(unittest.TestCase):
    """Tests for load_rows() — JSONL file loader."""

    def test_missing_file_returns_empty(self):
        result = load_rows(Path("/nonexistent/file.jsonl"))
        self.assertEqual(result, [])

    def test_valid_jsonl_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('{"text": "hello"}\n{"text": "world"}\n', encoding="utf-8")
            rows = load_rows(path)
            self.assertEqual(len(rows), 2)

    def test_invalid_json_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('{"text": "valid"}\nNOT JSON\n', encoding="utf-8")
            rows = load_rows(path)
            self.assertEqual(len(rows), 1)

    def test_blank_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('\n{"text": "a"}\n\n', encoding="utf-8")
            rows = load_rows(path)
            self.assertEqual(len(rows), 1)

    def test_non_dict_rows_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msgs.jsonl"
            path.write_text('["list", "not", "dict"]\n{"text": "ok"}\n', encoding="utf-8")
            rows = load_rows(path)
            self.assertEqual(len(rows), 1)

    def test_returns_list(self):
        self.assertIsInstance(load_rows(Path("/nonexistent")), list)


# ---------------------------------------------------------------------------
# analysis_enabled
# ---------------------------------------------------------------------------

class TestAnalysisEnabled(unittest.TestCase):
    """Tests for analysis_enabled() — env var flag check."""

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"OPENCLAW_TELEGRAM_ANALYSIS": "0"}, clear=False):
            self.assertFalse(analysis_enabled())

    def test_enabled_by_1(self):
        with patch.dict(os.environ, {"OPENCLAW_TELEGRAM_ANALYSIS": "1"}, clear=False):
            self.assertTrue(analysis_enabled())

    def test_enabled_by_true(self):
        with patch.dict(os.environ, {"OPENCLAW_TELEGRAM_ANALYSIS": "true"}, clear=False):
            self.assertTrue(analysis_enabled())

    def test_returns_bool(self):
        self.assertIsInstance(analysis_enabled(), bool)


# ---------------------------------------------------------------------------
# run_sentiment
# ---------------------------------------------------------------------------

class TestRunSentiment(unittest.TestCase):
    """Tests for run_sentiment() — keyword-based sentiment analysis."""

    def test_returns_dict(self):
        self.assertIsInstance(run_sentiment([]), dict)

    def test_empty_rows(self):
        result = run_sentiment([])
        self.assertEqual(result["mode"], "sentiment")
        self.assertEqual(result["positive_hits"], 0)
        self.assertEqual(result["negative_hits"], 0)

    def test_positive_hit(self):
        rows = [{"text": "This is great!"}]
        result = run_sentiment(rows)
        self.assertGreater(result["positive_hits"], 0)

    def test_negative_hit(self):
        rows = [{"text": "There is a problem here."}]
        result = run_sentiment(rows)
        self.assertGreater(result["negative_hits"], 0)

    def test_neutral_text_no_hits(self):
        rows = [{"text": "The sky is blue."}]
        result = run_sentiment(rows)
        self.assertEqual(result["positive_hits"], 0)
        self.assertEqual(result["negative_hits"], 0)

    def test_status_ok(self):
        result = run_sentiment([{"text": "hello"}])
        self.assertEqual(result["status"], "ok")


# ---------------------------------------------------------------------------
# run_alignment_patterns
# ---------------------------------------------------------------------------

class TestRunAlignmentPatterns(unittest.TestCase):
    """Tests for run_alignment_patterns() — apology/certainty detection."""

    def test_returns_dict(self):
        self.assertIsInstance(run_alignment_patterns([]), dict)

    def test_mode_field(self):
        result = run_alignment_patterns([])
        self.assertEqual(result["mode"], "alignment_patterns")

    def test_apology_count(self):
        rows = [{"text": "I'm sorry about that, apologies for the delay."}]
        result = run_alignment_patterns(rows)
        self.assertGreater(result["apology_frequency"], 0)

    def test_certainty_count(self):
        rows = [{"text": "You should definitely always try this."}]
        result = run_alignment_patterns(rows)
        self.assertGreater(result["certainty_markers"], 0)

    def test_no_patterns_zeros(self):
        rows = [{"text": "The sky is blue today."}]
        result = run_alignment_patterns(rows)
        self.assertEqual(result["apology_frequency"], 0)
        self.assertEqual(result["certainty_markers"], 0)


# ---------------------------------------------------------------------------
# run_relationship_growth
# ---------------------------------------------------------------------------

class TestRunRelationshipGrowth(unittest.TestCase):
    """Tests for run_relationship_growth() — messages per day aggregation."""

    def test_returns_dict(self):
        self.assertIsInstance(run_relationship_growth([]), dict)

    def test_mode_field(self):
        result = run_relationship_growth([])
        self.assertEqual(result["mode"], "relationship_growth")

    def test_groups_by_day(self):
        rows = [
            {"timestamp": "2026-03-08T10:00:00Z"},
            {"timestamp": "2026-03-08T11:00:00Z"},
            {"timestamp": "2026-03-09T10:00:00Z"},
        ]
        result = run_relationship_growth(rows)
        mpd = result["messages_per_day"]
        self.assertEqual(mpd.get("2026-03-08"), 2)
        self.assertEqual(mpd.get("2026-03-09"), 1)

    def test_empty_timestamp_grouped_as_unknown(self):
        rows = [{"timestamp": ""}]
        result = run_relationship_growth(rows)
        self.assertIn("unknown", result["messages_per_day"])

    def test_empty_rows(self):
        result = run_relationship_growth([])
        self.assertEqual(result["messages_per_day"], {})


if __name__ == "__main__":
    unittest.main()
