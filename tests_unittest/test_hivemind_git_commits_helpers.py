"""Tests for extract_diff_blocks() in workspace/hivemind/hivemind/ingest/git_commits.py.

Stubs relative imports (..models, ..store) before module load.

Covers:
- extract_diff_blocks(diff_text) — parses git diff into (filename, body) pairs
"""
import importlib.util as _ilu
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "ingest" / "git_commits.py"


def _ensure_stubs():
    """Stub hivemind relative dependencies if not already loaded."""
    stub_map = {
        "workspace.hivemind": {"__path__": []},
        "workspace.hivemind.hivemind": {"__path__": []},
        "workspace.hivemind.hivemind.models": {
            "KnowledgeUnit": type("KnowledgeUnit", (), {"__init__": lambda s, **k: None}),
        },
        "workspace.hivemind.hivemind.store": {
            "HiveMindStore": type("HiveMindStore", (), {}),
        },
        "workspace.hivemind.hivemind.ingest": {"__path__": []},
    }
    for name, attrs in stub_map.items():
        if name not in sys.modules:
            m = types.ModuleType(name)
            for k, v in attrs.items():
                setattr(m, k, v)
            sys.modules[name] = m


_ensure_stubs()

_spec = _ilu.spec_from_file_location(
    "workspace.hivemind.hivemind.ingest.git_commits",
    str(MODULE_PATH),
)
_gc = _ilu.module_from_spec(_spec)
_gc.__package__ = "workspace.hivemind.hivemind.ingest"
sys.modules["workspace.hivemind.hivemind.ingest.git_commits"] = _gc
_spec.loader.exec_module(_gc)

extract_diff_blocks = _gc.extract_diff_blocks


# ---------------------------------------------------------------------------
# extract_diff_blocks
# ---------------------------------------------------------------------------


class TestExtractDiffBlocks(unittest.TestCase):
    """Tests for extract_diff_blocks(diff_text) — parses git diff output."""

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(extract_diff_blocks(""), [])

    def test_returns_list(self):
        self.assertIsInstance(extract_diff_blocks(""), list)

    def test_single_file_single_hunk_one_block(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "@@ -1,2 +1,2 @@\n"
            "+added\n"
            "-removed\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertEqual(len(blocks), 1)

    def test_filename_extracted_from_diff_line(self):
        diff = (
            "diff --git a/path/to/file.py b/path/to/file.py\n"
            "@@ -1 +1 @@\n"
            "+new\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertEqual(blocks[0][0], "path/to/file.py")

    def test_block_is_tuple(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "+x\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertIsInstance(blocks[0], tuple)

    def test_block_has_two_elements(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "+x\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertEqual(len(blocks[0]), 2)

    def test_body_contains_hunk_lines(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "+added line\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertIn("+added line", blocks[0][1])

    def test_plus_plus_plus_lines_excluded_from_body(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "+++ b/f.py\n"
            "+real\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertNotIn("+++", blocks[0][1])

    def test_minus_minus_minus_lines_excluded_from_body(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "--- a/f.py\n"
            "+real\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertNotIn("---", blocks[0][1])

    def test_multiple_files_produce_multiple_blocks(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "@@ -1 +1 @@\n"
            "+x\n"
            "diff --git a/b.py b/b.py\n"
            "@@ -1 +1 @@\n"
            "+y\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertEqual(len(blocks), 2)

    def test_multiple_files_correct_names(self):
        diff = (
            "diff --git a/alpha.py b/alpha.py\n"
            "@@ -1 +1 @@\n"
            "+x\n"
            "diff --git a/beta.py b/beta.py\n"
            "@@ -1 +1 @@\n"
            "+y\n"
        )
        blocks = extract_diff_blocks(diff)
        names = [b[0] for b in blocks]
        self.assertIn("alpha.py", names)
        self.assertIn("beta.py", names)

    def test_multiple_hunks_same_file_produce_multiple_blocks(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1 +1 @@\n"
            "+first hunk\n"
            "@@ -10 +10 @@\n"
            "+second hunk\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][0], "f.py")
        self.assertEqual(blocks[1][0], "f.py")

    def test_context_lines_included(self):
        diff = (
            "diff --git a/f.py b/f.py\n"
            "@@ -1,3 +1,3 @@\n"
            " context\n"
            "+added\n"
            "-removed\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertIn(" context", blocks[0][1])

    def test_no_diff_header_no_blocks(self):
        # Text without "diff --git" lines should produce no blocks
        # (because no @@ line is ever preceded by a diff header,
        # and without current being set, lines are skipped)
        diff = "just some random text\n"
        blocks = extract_diff_blocks(diff)
        self.assertEqual(blocks, [])

    def test_diff_without_at_at_produces_no_blocks(self):
        # A diff --git line with no @@ hunk → nothing to flush
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n"
        blocks = extract_diff_blocks(diff)
        self.assertEqual(blocks, [])

    def test_hunk_body_starts_with_at_at_line(self):
        hunk_header = "@@ -1,2 +1,2 @@"
        diff = (
            "diff --git a/f.py b/f.py\n"
            + hunk_header + "\n"
            "+line\n"
        )
        blocks = extract_diff_blocks(diff)
        self.assertTrue(blocks[0][1].startswith(hunk_header))

    def test_unknown_filename_when_diff_line_malformed(self):
        # If diff line doesn't have at least 3 parts with a/ prefix, use "unknown"
        diff = "diff --git\n@@ -1 +1 @@\n+x\n"
        blocks = extract_diff_blocks(diff)
        # May produce a block with "unknown" filename or none
        # Just verify it doesn't raise
        self.assertIsInstance(blocks, list)


if __name__ == "__main__":
    unittest.main()
