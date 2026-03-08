"""Tests for store.sanitizer — sanitize(), diff(), sanitizer_version().

The sanitizer is security-critical: it prevents tag-Goodharting by stripping
governance tags before embedding. These tests verify that:
  - Tags are stripped from embedding input
  - Body text content is preserved
  - Audit diffs are accurate
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

from sanitizer import sanitize, diff, sanitizer_version, SANITIZER_VERSION, STATUS_PHRASES


class TestSanitize(unittest.TestCase):
    """Tests for sanitize() — tag stripping before embedding."""

    def test_plain_text_unchanged(self):
        text = "The routing system tracks memory attribution paths."
        self.assertEqual(sanitize(text), text)

    def test_empty_string_returns_empty(self):
        self.assertEqual(sanitize(""), "")

    def test_exec_micro_tag_stripped(self):
        text = "Content with [EXEC:MICRO] tag inside."
        result = sanitize(text)
        self.assertNotIn("[EXEC:MICRO]", result)
        self.assertIn("Content", result)
        self.assertIn("tag inside", result)

    def test_exec_gov_tag_stripped(self):
        text = "Content with [EXEC:GOV] governance tag."
        result = sanitize(text)
        self.assertNotIn("[EXEC:GOV]", result)

    def test_joint_tag_stripped(self):
        text = "[JOINT: c_lawd + Dali] The joint output content."
        result = sanitize(text)
        self.assertNotIn("[JOINT:", result)
        self.assertIn("joint output content", result)

    def test_upper_tag_stripped(self):
        text = "[UPPER:LAYER1] content continues."
        result = sanitize(text)
        self.assertNotIn("[UPPER:", result)
        self.assertIn("content continues", result)

    def test_case_insensitive_tag_stripping(self):
        text = "Test [exec:micro] and [Exec:Gov] and [EXEC:MICRO]."
        result = sanitize(text)
        self.assertNotIn("[exec:micro]", result)
        self.assertNotIn("[Exec:Gov]", result)
        self.assertNotIn("[EXEC:MICRO]", result)

    def test_gate_pass_phrase_stripped(self):
        text = "Gate result: GATE-INV004-PASS acknowledged."
        result = sanitize(text)
        self.assertNotIn("GATE-INV004-PASS", result)
        self.assertIn("acknowledged", result)

    def test_gate_rejection_phrase_stripped(self):
        text = "Decision: GATE-INV004-REJECTION logged."
        result = sanitize(text)
        self.assertNotIn("GATE-INV004-REJECTION", result)

    def test_isolation_verified_phrase_stripped(self):
        text = "isolation_verified: true was confirmed."
        result = sanitize(text)
        self.assertNotIn("isolation_verified: true", result)

    def test_embed_model_phrase_stripped(self):
        text = "embed_model: all-MiniLM-L6-v2 used."
        result = sanitize(text)
        self.assertNotIn("embed_model:", result)

    def test_whitespace_collapsed(self):
        # Multiple spaces → single space
        text = "word1   word2    word3"
        result = sanitize(text)
        self.assertNotIn("   ", result)

    def test_excess_newlines_collapsed(self):
        text = "para1\n\n\n\n\npara2"
        result = sanitize(text)
        # Should have at most 2 consecutive newlines
        self.assertNotIn("\n\n\n", result)

    def test_result_stripped(self):
        text = "  content  "
        result = sanitize(text)
        self.assertEqual(result, result.strip())

    def test_multiple_tags_all_stripped(self):
        text = "[EXEC:MICRO] first [JOINT: x] second [EXEC:GOV] third."
        result = sanitize(text)
        self.assertNotIn("[EXEC:MICRO]", result)
        self.assertNotIn("[JOINT:", result)
        self.assertNotIn("[EXEC:GOV]", result)
        self.assertIn("first", result)
        self.assertIn("second", result)
        self.assertIn("third", result)

    def test_sanitize_does_not_modify_input(self):
        # The docstring says "Does NOT modify the original text object"
        original = "Content [EXEC:MICRO] stays."
        original_id = id(original)
        sanitize(original)
        self.assertEqual(original, "Content [EXEC:MICRO] stays.")


class TestSanitizerVersion(unittest.TestCase):
    """Tests for sanitizer_version() and SANITIZER_VERSION constant."""

    def test_returns_string(self):
        self.assertIsInstance(sanitizer_version(), str)

    def test_returns_constant(self):
        self.assertEqual(sanitizer_version(), SANITIZER_VERSION)

    def test_version_is_semver_format(self):
        v = sanitizer_version()
        parts = v.split(".")
        self.assertEqual(len(parts), 3, f"Expected semver: {v!r}")
        for part in parts:
            self.assertTrue(part.isdigit(), f"Part not integer: {part!r}")

    def test_version_consistent_across_calls(self):
        self.assertEqual(sanitizer_version(), sanitizer_version())


class TestDiff(unittest.TestCase):
    """Tests for diff() — audit summary of sanitization changes."""

    def test_empty_strings_zero_diff(self):
        result = diff("", "")
        self.assertEqual(result["chars_removed"], 0)
        self.assertEqual(result["tags_removed"], [])
        self.assertEqual(result["status_phrases_removed"], [])

    def test_tags_removed_listed(self):
        original = "Content [EXEC:MICRO] here."
        san = sanitize(original)
        result = diff(original, san)
        self.assertIn("EXEC", result["tags_removed"][0])

    def test_status_phrases_removed_listed(self):
        original = "GATE-INV004-PASS was logged."
        san = sanitize(original)
        result = diff(original, san)
        self.assertGreater(len(result["status_phrases_removed"]), 0)

    def test_chars_removed_positive_when_content_removed(self):
        original = "Text [EXEC:MICRO] more."
        san = sanitize(original)
        result = diff(original, san)
        self.assertGreater(result["chars_removed"], 0)

    def test_chars_removed_zero_for_identical(self):
        text = "plain content"
        result = diff(text, text)
        self.assertEqual(result["chars_removed"], 0)

    def test_sanitizer_version_in_diff(self):
        result = diff("", "")
        self.assertIn("sanitizer_version", result)
        self.assertEqual(result["sanitizer_version"], SANITIZER_VERSION)

    def test_multiple_tags_all_in_removed_list(self):
        original = "A [EXEC:MICRO] B [EXEC:GOV] C."
        san = sanitize(original)
        result = diff(original, san)
        self.assertEqual(len(result["tags_removed"]), 2)


class TestStatusPhrases(unittest.TestCase):
    """Tests for STATUS_PHRASES — governance noise vocabulary."""

    def test_is_list(self):
        self.assertIsInstance(STATUS_PHRASES, list)

    def test_non_empty(self):
        self.assertGreater(len(STATUS_PHRASES), 0)

    def test_gate_pass_present(self):
        self.assertIn("GATE-INV004-PASS", STATUS_PHRASES)

    def test_gate_rejection_present(self):
        self.assertIn("GATE-INV004-REJECTION", STATUS_PHRASES)

    def test_isolation_verified_true_present(self):
        self.assertIn("isolation_verified: true", STATUS_PHRASES)

    def test_all_strings(self):
        for phrase in STATUS_PHRASES:
            self.assertIsInstance(phrase, str)


if __name__ == "__main__":
    unittest.main()
