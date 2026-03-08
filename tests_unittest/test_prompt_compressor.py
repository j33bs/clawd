"""Unit tests for workspace/agents/prompt_compressor.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.agents.prompt_compressor import compress_prompt, _important_lines


class TestImportantLines(unittest.TestCase):
    def test_finds_keyword_lines(self):
        text = "This must happen.\nSome other line.\nFailed to connect to api."
        lines = _important_lines(text, limit=5)
        self.assertTrue(any("must" in l for l in lines))
        self.assertTrue(any("api" in l.lower() for l in lines))

    def test_empty_text_returns_empty(self):
        self.assertEqual(_important_lines("", limit=5), [])

    def test_respects_limit(self):
        text = "\n".join(f"must do thing {i}" for i in range(20))
        lines = _important_lines(text, limit=4)
        self.assertLessEqual(len(lines), 4)

    def test_scores_by_keyword_count(self):
        # Line with 2 keywords should rank higher than line with 1
        text = "require token constraint check\nsome unrelated text\ngoal achieved"
        lines = _important_lines(text, limit=3)
        # First result should be the multi-keyword line
        self.assertIn("require token constraint check", lines[0])


class TestCompressPrompt(unittest.TestCase):
    def test_short_prompt_passthrough(self):
        short = "Hello world"
        result = compress_prompt(short, max_chars=7000)
        self.assertFalse(result["compressed"])
        self.assertEqual(result["text"], short)
        self.assertEqual(result["ratio"], 1.0)

    def test_long_prompt_compressed(self):
        long_text = "x " * 5000  # ~10000 chars
        result = compress_prompt(long_text, max_chars=7000)
        self.assertTrue(result["compressed"])
        self.assertLessEqual(len(result["text"]), 7000)
        self.assertLess(result["ratio"], 1.0)

    def test_compressed_contains_marker(self):
        long_text = "must include this: " + "a" * 8000
        result = compress_prompt(long_text, max_chars=7000)
        self.assertIn("[COMPRESSED_CONTEXT]", result["text"])

    def test_compressed_contains_head_and_tail(self):
        long_text = "HEADSTART " + "middle " * 2000 + " TAILEND"
        result = compress_prompt(long_text, max_chars=7000)
        # head should contain start, tail should have end
        self.assertIn("HEADSTART", result["text"])
        self.assertIn("TAILEND", result["text"])

    def test_returns_original_chars(self):
        text = "a" * 100
        result = compress_prompt(text, max_chars=7000)
        self.assertEqual(result["original_chars"], 100)

    def test_empty_string_passthrough(self):
        result = compress_prompt("", max_chars=7000)
        self.assertFalse(result["compressed"])
        self.assertEqual(result["text"], "")

    def test_exact_limit_passthrough(self):
        text = "x" * 7000
        result = compress_prompt(text, max_chars=7000)
        self.assertFalse(result["compressed"])

    def test_one_over_limit_compresses(self):
        text = "x" * 7001
        result = compress_prompt(text, max_chars=7000)
        self.assertTrue(result["compressed"])


if __name__ == "__main__":
    unittest.main()
