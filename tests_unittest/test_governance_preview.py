"""Tests for governance_preview — _int_to_roman, _format_governance_section,
_load_wander_log_entries, _load_findings_entries, generate_preview, render_preview."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import governance_preview as gp


class TestIntToRoman(unittest.TestCase):
    """Tests for _int_to_roman() — Roman numeral conversion."""

    def test_one(self):
        self.assertEqual(gp._int_to_roman(1), "I")

    def test_four(self):
        self.assertEqual(gp._int_to_roman(4), "IV")

    def test_five(self):
        self.assertEqual(gp._int_to_roman(5), "V")

    def test_nine(self):
        self.assertEqual(gp._int_to_roman(9), "IX")

    def test_ten(self):
        self.assertEqual(gp._int_to_roman(10), "X")

    def test_fourteen(self):
        self.assertEqual(gp._int_to_roman(14), "XIV")

    def test_forty(self):
        self.assertEqual(gp._int_to_roman(40), "XL")

    def test_fifty(self):
        self.assertEqual(gp._int_to_roman(50), "L")

    def test_ninety(self):
        self.assertEqual(gp._int_to_roman(90), "XC")

    def test_one_hundred(self):
        self.assertEqual(gp._int_to_roman(100), "C")

    def test_four_hundred(self):
        self.assertEqual(gp._int_to_roman(400), "CD")

    def test_five_hundred(self):
        self.assertEqual(gp._int_to_roman(500), "D")

    def test_nine_hundred(self):
        self.assertEqual(gp._int_to_roman(900), "CM")

    def test_one_thousand(self):
        self.assertEqual(gp._int_to_roman(1000), "M")

    # Real governance section numbers
    def test_xcii_92(self):
        self.assertEqual(gp._int_to_roman(92), "XCII")

    def test_cxliii_143(self):
        self.assertEqual(gp._int_to_roman(143), "CXLIII")

    def test_clxi_161(self):
        self.assertEqual(gp._int_to_roman(161), "CLXI")

    def test_clxii_162(self):
        self.assertEqual(gp._int_to_roman(162), "CLXII")

    def test_lxxxii_82(self):
        self.assertEqual(gp._int_to_roman(82), "LXXXII")

    def test_clvi_156(self):
        self.assertEqual(gp._int_to_roman(156), "CLVI")

    def test_current_section_count_plus_one(self):
        """161 + 1 = 162 = CLXII — the next section after current state."""
        self.assertEqual(gp._int_to_roman(162), "CLXII")


class TestFormatGovernanceSection(unittest.TestCase):
    """Tests for _format_governance_section() — pure section text formatting."""

    def test_output_starts_with_roman_header(self):
        text = gp._format_governance_section(1, "Test question?", author="Claude Code")
        self.assertTrue(text.startswith("## I."))

    def test_author_in_header(self):
        text = gp._format_governance_section(1, "Test?", author="Dali")
        self.assertIn("Dali", text)

    def test_question_text_included(self):
        text = gp._format_governance_section(1, "What is consciousness?")
        self.assertIn("What is consciousness?", text)

    def test_long_question_appears_in_body(self):
        """Long question text: title_q truncation is computed but the header only shows
        author + date (not question text). The full question always appears in the body."""
        long_q = "This is a very long question that exceeds eighty characters for testing " + "x" * 50
        text = gp._format_governance_section(1, long_q)
        # Full question text is in the body (not the header)
        self.assertIn("This is a very long question", text)
        # Header is just roman + author + date — no question text
        header_line = text.splitlines()[0]
        self.assertNotIn("This is a very long question", header_line)

    def test_question_mark_stripped_from_title(self):
        text = gp._format_governance_section(10, "Is this a question?")
        # Title strip: question mark should be removed from title
        lines = text.splitlines()
        header = lines[0]
        self.assertNotIn("?", header)

    def test_exec_micro_tag_present(self):
        text = gp._format_governance_section(1, "A question")
        self.assertIn("[EXEC:MICRO]", text)

    def test_human_review_note_present(self):
        text = gp._format_governance_section(1, "A question")
        self.assertIn("jeebs", text)

    def test_seed_topic_included_when_provided(self):
        text = gp._format_governance_section(1, "A question", seed_topic="routing_theory")
        self.assertIn("routing_theory", text)

    def test_seed_topic_omitted_when_empty(self):
        text = gp._format_governance_section(1, "A question", seed_topic="")
        self.assertNotIn("Seed topic:", text)

    def test_novelty_metrics_included_when_nonzero(self):
        text = gp._format_governance_section(1, "A question", overlap_max=0.3, similarity_max=0.7)
        self.assertIn("overlap_max=0.300", text)
        self.assertIn("similarity_max=0.700", text)

    def test_novelty_metrics_omitted_when_zero(self):
        text = gp._format_governance_section(1, "A question", overlap_max=0.0, similarity_max=0.0)
        self.assertNotIn("overlap_max", text)

    def test_section_162_roman_numeral_correct(self):
        text = gp._format_governance_section(162, "Next question")
        self.assertTrue(text.startswith("## CLXII."))


class TestLoadWanderLogEntries(unittest.TestCase):
    """Tests for _load_wander_log_entries()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_log(self, content: str) -> Path:
        path = self._tmp / "wander_log.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_missing_file_returns_empty(self):
        result = gp._load_wander_log_entries(self._tmp / "nonexistent.md")
        self.assertEqual(result, [])

    def test_header_row_skipped(self):
        content = "| date_utc | question | overlap | similarity | seed |\n"
        path = self._write_log(content)
        result = gp._load_wander_log_entries(path)
        self.assertEqual(result, [])

    def test_separator_row_skipped(self):
        content = "| --- | --- | --- | --- | --- |\n"
        path = self._write_log(content)
        result = gp._load_wander_log_entries(path)
        self.assertEqual(result, [])

    def test_valid_row_parsed(self):
        content = "| 2026-03-08 | What is memory? | 0.3 | 0.5 | routing |\n"
        path = self._write_log(content)
        result = gp._load_wander_log_entries(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question"], "What is memory?")
        self.assertAlmostEqual(result[0]["overlap_max"], 0.3)
        self.assertAlmostEqual(result[0]["similarity_max"], 0.5)
        self.assertEqual(result[0]["seed_topic"], "routing")

    def test_last_n_entries_returned(self):
        rows = [f"| 2026-03-0{i} | Q{i} | 0.{i} | 0.{i} | topic{i} |" for i in range(1, 8)]
        path = self._write_log("\n".join(rows) + "\n")
        result = gp._load_wander_log_entries(path, last_n=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1]["question"], "Q7")

    def test_non_table_lines_ignored(self):
        content = (
            "# Wander Log\n\n"
            "Some prose here.\n\n"
            "| 2026-03-08 | Q1 | 0.3 | 0.5 | t1 |\n"
        )
        path = self._write_log(content)
        result = gp._load_wander_log_entries(path)
        self.assertEqual(len(result), 1)


class TestLoadFindingsEntries(unittest.TestCase):
    """Tests for _load_findings_entries()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_empty(self):
        result = gp._load_findings_entries(self._tmp / "nonexistent.json")
        self.assertEqual(result, [])

    def test_questions_loaded(self):
        path = self._tmp / "findings.json"
        path.write_text(json.dumps({"questions_generated": ["Q1", "Q2", "Q3"]}), encoding="utf-8")
        result = gp._load_findings_entries(path)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["question"], "Q1")

    def test_invalid_json_returns_empty(self):
        path = self._tmp / "findings.json"
        path.write_text("not json", encoding="utf-8")
        result = gp._load_findings_entries(path)
        self.assertEqual(result, [])

    def test_non_string_questions_filtered(self):
        path = self._tmp / "findings.json"
        path.write_text(json.dumps({"questions_generated": ["Valid", 42, None, "Also valid"]}),
                        encoding="utf-8")
        result = gp._load_findings_entries(path)
        self.assertEqual(len(result), 2)


class TestGeneratePreview(unittest.TestCase):
    """Tests for generate_preview() — main preview logic."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)
        # Redirect wanderer paths
        self._orig_wander = gp.WANDER_LOG
        self._orig_findings = gp.FINDINGS_FILE
        self._orig_oq = gp.OQ_PATH
        self._orig_sc = gp.SECTION_COUNT_FILE
        gp.WANDER_LOG = self._tmp / "wander_log.md"
        gp.FINDINGS_FILE = self._tmp / "findings.json"
        gp.OQ_PATH = self._tmp / "OPEN_QUESTIONS.md"
        gp.SECTION_COUNT_FILE = self._tmp / ".section_count"

    def tearDown(self):
        gp.WANDER_LOG = self._orig_wander
        gp.FINDINGS_FILE = self._orig_findings
        gp.OQ_PATH = self._orig_oq
        gp.SECTION_COUNT_FILE = self._orig_sc
        self._tmpdir.cleanup()

    def test_returns_status_key(self):
        """generate_preview() always returns a 'status' key."""
        result = gp.generate_preview()
        self.assertIn("status", result)
        self.assertIn(result["status"], ("ok", "no_entries"))

    def test_sections_generated_from_wander_log(self):
        gp.WANDER_LOG.write_text(
            "| 2026-03-08 | What is routing? | 0.3 | 0.5 | routing |\n"
            "| 2026-03-08 | What is memory? | 0.2 | 0.4 | memory |\n",
            encoding="utf-8",
        )
        gp.SECTION_COUNT_FILE.write_text("161\n", encoding="utf-8")
        result = gp.generate_preview(n=2)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["sections"]), 2)

    def test_sections_numbered_from_base_count(self):
        gp.WANDER_LOG.write_text(
            "| 2026-03-08 | Q1? | 0.3 | 0.5 | t |\n",
            encoding="utf-8",
        )
        gp.SECTION_COUNT_FILE.write_text("100\n", encoding="utf-8")
        result = gp.generate_preview(n=1)
        # base = 100, next = 101
        section = result["sections"][0]
        self.assertEqual(section["proposed_section_number"], 101)
        self.assertEqual(section["proposed_roman"], "CI")

    def test_warning_always_present(self):
        gp.WANDER_LOG.write_text("| 2026-03-08 | Q? | 0.3 | 0.5 | t |\n", encoding="utf-8")
        gp.SECTION_COUNT_FILE.write_text("10\n", encoding="utf-8")
        result = gp.generate_preview(n=1)
        self.assertIn("warning", result)
        self.assertIn("jeebs", result["warning"])


class TestRenderPreview(unittest.TestCase):
    """Tests for render_preview() — pure markdown rendering."""

    def test_no_sections_returns_no_entries_message(self):
        preview = {"status": "no_entries", "source": "wander_log", "sections": [], "warning": ""}
        text = gp.render_preview(preview)
        self.assertIn("No entries to preview", text)

    def test_sections_rendered(self):
        preview = {
            "status": "ok",
            "source": "wander_log",
            "base_section_count": 161,
            "sections": [{"text": "## CLXII. Claude Code — 2026-03-08\n\nThe question.\n"}],
            "warning": "Do not auto-file",
        }
        text = gp.render_preview(preview)
        self.assertIn("CLXII", text)
        self.assertIn("The question.", text)

    def test_header_present(self):
        preview = {"status": "ok", "source": "wander_log", "base_section_count": 5,
                   "sections": [], "warning": "Review required"}
        text = gp.render_preview(preview)
        self.assertIn("Governance Section Preview", text)


if __name__ == "__main__":
    unittest.main()
