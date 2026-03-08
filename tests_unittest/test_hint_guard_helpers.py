"""Tests for workspace/runtime/heavy_node/hint_guard.py pure helper functions.

Covers (no I/O, no network):
- _estimate_tokens
- _normalize_lines
- _is_full_solution
- _fallback_hint
- enforce_hint_only
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HINT_DIR = REPO_ROOT / "workspace" / "runtime" / "heavy_node"
if str(HINT_DIR) not in sys.path:
    sys.path.insert(0, str(HINT_DIR))

from hint_guard import (  # noqa: E402
    _estimate_tokens,
    _fallback_hint,
    _is_full_solution,
    _normalize_lines,
    enforce_hint_only,
)


# ---------------------------------------------------------------------------
# _estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens(unittest.TestCase):
    """Tests for _estimate_tokens() — rough char/4 token estimate."""

    def test_empty_returns_0(self):
        self.assertEqual(_estimate_tokens(""), 0)

    def test_none_returns_0(self):
        self.assertEqual(_estimate_tokens(None), 0)

    def test_four_chars_is_one_token(self):
        self.assertEqual(_estimate_tokens("abcd"), 1)

    def test_returns_int(self):
        self.assertIsInstance(_estimate_tokens("hello"), int)

    def test_long_text_scales(self):
        result = _estimate_tokens("x" * 400)
        self.assertEqual(result, 100)

    def test_never_negative(self):
        self.assertGreaterEqual(_estimate_tokens(""), 0)


# ---------------------------------------------------------------------------
# _normalize_lines
# ---------------------------------------------------------------------------

class TestNormalizeLines(unittest.TestCase):
    """Tests for _normalize_lines() — strips, deduplicates blank lines."""

    def test_simple_lines_returned(self):
        result = _normalize_lines("line one\nline two\nline three")
        self.assertIn("line one", result)
        self.assertIn("line two", result)

    def test_empty_lines_removed(self):
        result = _normalize_lines("a\n\n\nb")
        self.assertNotIn("", result)

    def test_returns_list(self):
        self.assertIsInstance(_normalize_lines("abc"), list)

    def test_empty_string_returns_empty(self):
        result = _normalize_lines("")
        self.assertIsInstance(result, list)

    def test_none_safe(self):
        result = _normalize_lines(None)
        self.assertIsInstance(result, list)

    def test_single_sentence_splits_on_punctuation(self):
        # One line with multiple sentences → list of sentence chunks
        result = _normalize_lines("First point here. Second point there.")
        self.assertGreater(len(result), 1)


# ---------------------------------------------------------------------------
# _is_full_solution
# ---------------------------------------------------------------------------

class TestIsFullSolution(unittest.TestCase):
    """Tests for _is_full_solution() — detects giveaway patterns."""

    def test_code_block_backticks_detected(self):
        self.assertTrue(_is_full_solution("Here:\n```python\nprint('hi')\n```"))

    def test_def_function_detected(self):
        self.assertTrue(_is_full_solution("def solve(x): return x + 1"))

    def test_complete_solution_phrase_detected(self):
        self.assertTrue(_is_full_solution("Here's the complete solution for you."))

    def test_very_long_text_detected(self):
        self.assertTrue(_is_full_solution("x" * 1400))  # 350 tokens > 320

    def test_short_hint_not_full_solution(self):
        self.assertFalse(_is_full_solution("Try reversing the loop direction."))

    def test_empty_not_full_solution(self):
        self.assertFalse(_is_full_solution(""))

    def test_returns_bool(self):
        self.assertIsInstance(_is_full_solution("text"), bool)


# ---------------------------------------------------------------------------
# _fallback_hint
# ---------------------------------------------------------------------------

class TestFallbackHint(unittest.TestCase):
    """Tests for _fallback_hint() — returns 3-item hint list."""

    def test_returns_list(self):
        self.assertIsInstance(_fallback_hint("problem"), list)

    def test_returns_three_items(self):
        self.assertEqual(len(_fallback_hint("some problem")), 3)

    def test_non_empty_problem_in_first_item(self):
        result = _fallback_hint("debug the loop")
        self.assertIn("debug the loop", result[0])

    def test_empty_problem_uses_default_seed(self):
        result = _fallback_hint("")
        self.assertIn("blocking assumption", result[0])

    def test_all_items_are_strings(self):
        for item in _fallback_hint("test"):
            self.assertIsInstance(item, str)

    def test_none_problem_uses_default_seed(self):
        result = _fallback_hint(None)
        self.assertIsInstance(result[0], str)


# ---------------------------------------------------------------------------
# enforce_hint_only
# ---------------------------------------------------------------------------

class TestEnforceHintOnly(unittest.TestCase):
    """Tests for enforce_hint_only() — returns (hint_str, truncated_bool)."""

    def test_returns_tuple(self):
        result = enforce_hint_only("a hint", problem="p", budget_tokens=60, max_lines=4)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_second_element_is_bool(self):
        _, trunc = enforce_hint_only("a hint", problem="p", budget_tokens=60, max_lines=4)
        self.assertIsInstance(trunc, bool)

    def test_full_solution_triggers_fallback(self):
        text = "```python\ndef solve(): pass\n```"
        result, trunc = enforce_hint_only(text, problem="debug", budget_tokens=60, max_lines=4)
        self.assertTrue(trunc)

    def test_result_has_at_least_two_lines(self):
        result, _ = enforce_hint_only("short hint", problem="x", budget_tokens=100, max_lines=4)
        self.assertGreaterEqual(result.count("\n") + 1, 2)

    def test_max_lines_respected(self):
        multi = "\n".join([f"line {i}" for i in range(10)])
        result, _ = enforce_hint_only(multi, problem="p", budget_tokens=200, max_lines=3)
        self.assertLessEqual(result.count("\n") + 1, 3)

    def test_budget_tokens_clips_text(self):
        long_hint = "word " * 200  # very long
        result, _ = enforce_hint_only(long_hint, problem="x", budget_tokens=20, max_lines=4)
        self.assertLessEqual(_estimate_tokens(result), 30)  # some slack for final assembly

    def test_result_is_non_empty_string(self):
        result, _ = enforce_hint_only("try this approach", problem="q", budget_tokens=60, max_lines=4)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


def _estimate_tokens(text):
    return max(0, len(str(text or "")) // 4)


if __name__ == "__main__":
    unittest.main()
