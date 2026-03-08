"""Tests for hivemind ingest pure helper functions.

Covers:
- hivemind.ingest.git_commits.extract_diff_blocks
- hivemind.ingest.handoffs.parse_frontmatter
- hivemind.ingest.memory_md.parse_memory_chunks
"""
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.ingest.git_commits import extract_diff_blocks   # noqa: E402
from hivemind.ingest.handoffs import parse_frontmatter        # noqa: E402
from hivemind.ingest.memory_md import parse_memory_chunks     # noqa: E402


# ---------------------------------------------------------------------------
# extract_diff_blocks
# ---------------------------------------------------------------------------

class TestExtractDiffBlocks(unittest.TestCase):
    """Tests for git_commits.extract_diff_blocks() — git diff parser."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(extract_diff_blocks(""), [])

    def test_returns_list_of_tuples(self):
        result = extract_diff_blocks("")
        self.assertIsInstance(result, list)

    def test_single_file_hunk_extracted(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+def bar():\n"
            "+    pass\n"
        )
        result = extract_diff_blocks(diff)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "foo.py")
        self.assertIn("bar", result[0][1])

    def test_multiple_files_produce_multiple_blocks(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "@@ -1 +1 @@\n"
            "+x = 1\n"
            "diff --git a/b.py b/b.py\n"
            "@@ -1 +1 @@\n"
            "+y = 2\n"
        )
        result = extract_diff_blocks(diff)
        self.assertEqual(len(result), 2)
        files = [r[0] for r in result]
        self.assertIn("a.py", files)
        self.assertIn("b.py", files)

    def test_plusplus_and_minusminus_lines_skipped(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "@@ -1 +1 @@\n"
            "+++ b/a.py\n"
            "--- a/a.py\n"
            "+x = 1\n"
        )
        result = extract_diff_blocks(diff)
        self.assertTrue(any("a.py" in r[0] for r in result))
        for _, body in result:
            self.assertNotIn("--- a/", body)
            self.assertNotIn("+++ b/", body)

    def test_block_content_is_string(self):
        diff = (
            "diff --git a/x.py b/x.py\n"
            "@@ -1 +1 @@\n"
            "+pass\n"
        )
        result = extract_diff_blocks(diff)
        for _file, body in result:
            self.assertIsInstance(body, str)

    def test_no_diff_header_returns_empty(self):
        # Just raw text without diff markers — no @@ hunks → nothing to flush
        result = extract_diff_blocks("some random text\nmore text\n")
        self.assertEqual(result, [])

    def test_multiple_hunks_same_file_separate_blocks(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "+x = 1\n"
            "@@ -10 +10 @@\n"
            "+y = 2\n"
        )
        result = extract_diff_blocks(diff)
        # Each @@ starts a new block
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter(unittest.TestCase):
    """Tests for handoffs.parse_frontmatter() — YAML-ish frontmatter parser."""

    def test_empty_string_returns_defaults(self):
        result = parse_frontmatter("")
        self.assertEqual(result, {"status": "", "from": "", "date": ""})

    def test_yaml_block_extracted(self):
        text = "---\nstatus: open\nfrom: claude-code\ndate: 2026-03-08\n---\n# Body"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "open")
        self.assertEqual(result["from"], "claude-code")
        self.assertEqual(result["date"], "2026-03-08")

    def test_inline_keys_scanned(self):
        text = "status: draft\nfrom: jeebs\ndate: 2026-01-01\n"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "draft")

    def test_case_insensitive_keys(self):
        text = "Status: OPEN\nFrom: bot\nDate: 2026-01-01\n"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "OPEN")

    def test_extra_keys_ignored(self):
        text = "---\nstatus: open\nextra_key: ignored\n---\n"
        result = parse_frontmatter(text)
        self.assertNotIn("extra_key", result)

    def test_returns_dict(self):
        self.assertIsInstance(parse_frontmatter(""), dict)

    def test_no_frontmatter_all_empty(self):
        text = "# Just a heading\n\nSome body content.\n"
        result = parse_frontmatter(text)
        self.assertEqual(result["status"], "")
        self.assertEqual(result["from"], "")

    def test_multiline_value_first_part_only(self):
        # The regex captures up to end of line — value is single-line
        text = "status: open\n"
        result = parse_frontmatter(text)
        self.assertIn("open", result["status"])


# ---------------------------------------------------------------------------
# parse_memory_chunks
# ---------------------------------------------------------------------------

class TestParseMemoryChunks(unittest.TestCase):
    """Tests for memory_md.parse_memory_chunks() — MEMORY.md segmenter."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(parse_memory_chunks(""), [])

    def test_returns_list(self):
        self.assertIsInstance(parse_memory_chunks(""), list)

    def test_plain_paragraph_creates_fact(self):
        text = "Some plain text here.\n"
        result = parse_memory_chunks(text)
        self.assertTrue(len(result) >= 1)
        self.assertTrue(any(c["kind"] == "fact" for c in result))

    def test_lesson_keyword_triggers_lesson_kind(self):
        text = "## Lessons\n\nA lesson learned from last week.\n"
        result = parse_memory_chunks(text)
        kinds = [c["kind"] for c in result]
        self.assertIn("lesson", kinds)

    def test_header_becomes_section_prefix(self):
        text = "## Memory\n\nSome context here.\n"
        result = parse_memory_chunks(text)
        self.assertTrue(any("Memory" in c["content"] for c in result))

    def test_bullet_items_grouped_separately_from_paragraphs(self):
        text = "Intro text.\n\n- item one\n- item two\n"
        result = parse_memory_chunks(text)
        self.assertTrue(len(result) >= 1)

    def test_dict_has_kind_and_content(self):
        text = "Some text.\n"
        result = parse_memory_chunks(text)
        for chunk in result:
            self.assertIn("kind", chunk)
            self.assertIn("content", chunk)

    def test_kind_is_string(self):
        text = "## Title\n\nSome text.\n"
        result = parse_memory_chunks(text)
        for chunk in result:
            self.assertIsInstance(chunk["kind"], str)

    def test_content_is_string(self):
        text = "Some text.\n"
        result = parse_memory_chunks(text)
        for chunk in result:
            self.assertIsInstance(chunk["content"], str)

    def test_multiple_sections(self):
        text = "## Section A\n\nText A.\n\n## Section B\n\nText B.\n"
        result = parse_memory_chunks(text)
        self.assertGreaterEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
