"""Tests for additional pure helpers in workspace/scripts/policy_router.py.

Covers functions not yet tested in test_policy_router_pure_helpers.py:
- estimate_tokens
- _truncate_text
- _looks_like_constraint_line
- _coerce_positive_int
- _contains_phrase
- _is_subagent_context
- _count_bullets
- _count_file_paths
- _new_request_id
- _policy_strict_enabled
- _extract_text_from_payload
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import policy_router as _pr  # noqa: E402

estimate_tokens = _pr.estimate_tokens
_truncate_text = _pr._truncate_text
_looks_like_constraint_line = _pr._looks_like_constraint_line
_coerce_positive_int = _pr._coerce_positive_int
_contains_phrase = _pr._contains_phrase
_is_subagent_context = _pr._is_subagent_context
_is_oracle_priority_context = _pr._is_oracle_priority_context
_is_oracle_preemptable_provider = _pr._is_oracle_preemptable_provider
_oracle_priority_gate = _pr._oracle_priority_gate
_count_bullets = _pr._count_bullets
_count_file_paths = _pr._count_file_paths
_new_request_id = _pr._new_request_id
_policy_strict_enabled = _pr._policy_strict_enabled
_extract_text_from_payload = _pr._extract_text_from_payload


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens(unittest.TestCase):
    """Tests for estimate_tokens() — rough character-based token count."""

    def test_empty_string_minimum_from_offset(self):
        # max(1, (0 + 200) // 4) = max(1, 50) = 50
        result = estimate_tokens("")
        self.assertGreaterEqual(result, 1)

    def test_short_text(self):
        # (len("hello") + 200) // 4 = 205 // 4 = 51
        result = estimate_tokens("hello")
        self.assertGreater(result, 0)

    def test_longer_text(self):
        text = "a" * 800
        # (800 + 200) // 4 = 250
        self.assertEqual(estimate_tokens(text), 250)

    def test_returns_positive_int(self):
        self.assertIsInstance(estimate_tokens("any text"), int)
        self.assertGreater(estimate_tokens("any text"), 0)

    def test_grows_with_length(self):
        short = estimate_tokens("hi")
        long = estimate_tokens("x" * 1000)
        self.assertGreater(long, short)


# ---------------------------------------------------------------------------
# _truncate_text
# ---------------------------------------------------------------------------

class TestTruncateText(unittest.TestCase):
    """Tests for _truncate_text() — clip to max_chars."""

    def test_short_text_unchanged(self):
        self.assertEqual(_truncate_text("hello", 100), "hello")

    def test_text_over_limit_clipped(self):
        result = _truncate_text("abcdefghij", 5)
        self.assertEqual(result, "abcde")

    def test_exact_length_unchanged(self):
        self.assertEqual(_truncate_text("hello", 5), "hello")

    def test_none_max_chars_returns_full(self):
        text = "hello world"
        self.assertEqual(_truncate_text(text, None), text)

    def test_small_max_chars_clips(self):
        # 0 is falsy so doesn't truncate; use 3 explicitly
        result = _truncate_text("hello", 3)
        self.assertEqual(result, "hel")

    def test_returns_string(self):
        self.assertIsInstance(_truncate_text("text", 10), str)


# ---------------------------------------------------------------------------
# _looks_like_constraint_line
# ---------------------------------------------------------------------------

class TestLooksLikeConstraintLine(unittest.TestCase):
    """Tests for _looks_like_constraint_line() — regex constraint detection."""

    def test_must_keyword(self):
        self.assertTrue(_looks_like_constraint_line("You must not share credentials"))

    def test_constraint_keyword(self):
        self.assertTrue(_looks_like_constraint_line("constraint: always verify"))

    def test_never_keyword(self):
        self.assertTrue(_looks_like_constraint_line("Never exceed the budget limit"))

    def test_system_prefix(self):
        self.assertTrue(_looks_like_constraint_line("System: enforce policy"))

    def test_policy_prefix(self):
        self.assertTrue(_looks_like_constraint_line("Policy: local-first routing"))

    def test_plain_line_false(self):
        self.assertFalse(_looks_like_constraint_line("Hello there, how are you?"))

    def test_empty_string_false(self):
        self.assertFalse(_looks_like_constraint_line(""))

    def test_whitespace_only_false(self):
        self.assertFalse(_looks_like_constraint_line("   "))

    def test_governance_keyword(self):
        self.assertTrue(_looks_like_constraint_line("governance requires consensus"))

    def test_returns_bool(self):
        self.assertIsInstance(_looks_like_constraint_line("test"), bool)


# ---------------------------------------------------------------------------
# _coerce_positive_int
# ---------------------------------------------------------------------------

class TestCoercePositiveInt(unittest.TestCase):
    """Tests for _coerce_positive_int() — try int, fallback on non-positive."""

    def test_valid_positive_int_string(self):
        self.assertEqual(_coerce_positive_int("5", 10), 5)

    def test_valid_positive_int(self):
        self.assertEqual(_coerce_positive_int(7, 10), 7)

    def test_zero_returns_fallback(self):
        self.assertEqual(_coerce_positive_int(0, 10), 10)

    def test_negative_returns_fallback(self):
        self.assertEqual(_coerce_positive_int(-3, 10), 10)

    def test_non_numeric_string_returns_fallback(self):
        self.assertEqual(_coerce_positive_int("abc", 10), 10)

    def test_none_returns_fallback(self):
        self.assertEqual(_coerce_positive_int(None, 42), 42)

    def test_float_string_truncates(self):
        # int("3.7") raises ValueError → fallback
        self.assertEqual(_coerce_positive_int("3.7", 99), 99)


# ---------------------------------------------------------------------------
# _contains_phrase
# ---------------------------------------------------------------------------

class TestContainsPhrase(unittest.TestCase):
    """Tests for _contains_phrase() — word-boundary phrase match."""

    def test_found_exact(self):
        self.assertTrue(_contains_phrase("run the tests now", "run the tests"))

    def test_not_found(self):
        self.assertFalse(_contains_phrase("hello world", "goodbye"))

    def test_case_insensitive(self):
        self.assertTrue(_contains_phrase("Run The Tests", "run the tests"))

    def test_empty_text_returns_false(self):
        self.assertFalse(_contains_phrase("", "word"))

    def test_empty_phrase_returns_false(self):
        self.assertFalse(_contains_phrase("hello", ""))

    def test_both_empty_returns_false(self):
        self.assertFalse(_contains_phrase("", ""))

    def test_returns_bool(self):
        self.assertIsInstance(_contains_phrase("a b c", "a b"), bool)


# ---------------------------------------------------------------------------
# _is_subagent_context
# ---------------------------------------------------------------------------

class TestIsSubagentContext(unittest.TestCase):
    """Tests for _is_subagent_context() — detect subagent context dict."""

    def test_subagent_key_true(self):
        self.assertTrue(_is_subagent_context({"subagent": True}))

    def test_is_subagent_key_true(self):
        self.assertTrue(_is_subagent_context({"is_subagent": True}))

    def test_agent_class_worker(self):
        self.assertTrue(_is_subagent_context({"agent_class": "worker"}))

    def test_node_role_tool(self):
        self.assertTrue(_is_subagent_context({"node_role": "tool"}))

    def test_empty_dict_false(self):
        self.assertFalse(_is_subagent_context({}))

    def test_non_dict_false(self):
        self.assertFalse(_is_subagent_context(None))
        self.assertFalse(_is_subagent_context("subagent"))

    def test_unrelated_keys_false(self):
        self.assertFalse(_is_subagent_context({"intent": "governance", "user": "jeebs"}))

    def test_returns_bool(self):
        self.assertIsInstance(_is_subagent_context({}), bool)


class TestOraclePriorityHelpers(unittest.TestCase):
    def test_oracle_priority_context_detected(self):
        self.assertTrue(_is_oracle_priority_context({"oracle_priority": True}))
        self.assertTrue(_is_oracle_priority_context({"source_surface": "source_ui_oracle"}))

    def test_oracle_priority_context_false_for_normal_task(self):
        self.assertFalse(_is_oracle_priority_context({"source_surface": "telegram"}))

    def test_preemptable_provider_matches_local_vllm(self):
        self.assertTrue(_is_oracle_preemptable_provider("local_vllm_assistant"))
        self.assertTrue(_is_oracle_preemptable_provider("local_vllm_coder"))
        self.assertFalse(_is_oracle_preemptable_provider("groq"))

    def test_oracle_priority_gate_bypasses_when_module_missing(self):
        with patch.object(_pr, "_oracle_priority", None):
            result = _oracle_priority_gate("local_vllm_assistant", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["waited_ms"], 0)

    def test_oracle_priority_gate_waits_for_clear(self):
        class FakePriority:
            @staticmethod
            def get_active_lease():
                return {"owner": "oracle", "purpose": "source_ui_oracle"}

            @staticmethod
            def wait_for_clear(*, max_wait_seconds, poll_interval):
                return {"cleared": True, "waited_seconds": 0.5, "active": None}

        with patch.object(_pr, "_oracle_priority", FakePriority()):
            result = _oracle_priority_gate("local_vllm_assistant", {"source_surface": "discord"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["waited_ms"], 500)

    def test_oracle_priority_gate_bypasses_oracle_context(self):
        class FakePriority:
            @staticmethod
            def get_active_lease():
                return {"owner": "oracle", "purpose": "source_ui_oracle"}

        with patch.object(_pr, "_oracle_priority", FakePriority()):
            result = _oracle_priority_gate("local_vllm_assistant", {"source_surface": "source_ui_oracle"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["waited_ms"], 0)


# ---------------------------------------------------------------------------
# _count_bullets
# ---------------------------------------------------------------------------

class TestCountBullets(unittest.TestCase):
    """Tests for _count_bullets() — count markdown list items."""

    def test_empty_text_zero(self):
        self.assertEqual(_count_bullets(""), 0)

    def test_none_zero(self):
        self.assertEqual(_count_bullets(None), 0)

    def test_dash_bullets(self):
        text = "- item one\n- item two\n- item three"
        self.assertEqual(_count_bullets(text), 3)

    def test_asterisk_bullets(self):
        text = "* alpha\n* beta"
        self.assertEqual(_count_bullets(text), 2)

    def test_numbered_list(self):
        text = "1. first\n2. second\n3. third"
        self.assertEqual(_count_bullets(text), 3)

    def test_mixed_list(self):
        text = "- item\n1. numbered\n* star"
        self.assertEqual(_count_bullets(text), 3)

    def test_no_list_zero(self):
        text = "Just plain text with no bullets"
        self.assertEqual(_count_bullets(text), 0)

    def test_returns_int(self):
        self.assertIsInstance(_count_bullets("- a"), int)


# ---------------------------------------------------------------------------
# _count_file_paths
# ---------------------------------------------------------------------------

class TestCountFilePaths(unittest.TestCase):
    """Tests for _count_file_paths() — count file path patterns."""

    def test_empty_text_zero(self):
        self.assertEqual(_count_file_paths(""), 0)

    def test_none_zero(self):
        self.assertEqual(_count_file_paths(None), 0)

    def test_single_path(self):
        result = _count_file_paths("See workspace/scripts/policy_router.py")
        self.assertGreater(result, 0)

    def test_multiple_paths(self):
        text = "Files: src/main.py and tests/test_foo.py are affected."
        result = _count_file_paths(text)
        self.assertGreater(result, 0)

    def test_no_paths(self):
        result = _count_file_paths("no file paths here at all")
        self.assertEqual(result, 0)

    def test_returns_int(self):
        self.assertIsInstance(_count_file_paths("a/b.py"), int)


# ---------------------------------------------------------------------------
# _new_request_id
# ---------------------------------------------------------------------------

class TestNewRequestId(unittest.TestCase):
    """Tests for _new_request_id() — unique prefixed request ID."""

    def test_default_prefix(self):
        result = _new_request_id()
        self.assertTrue(result.startswith("req-"))

    def test_custom_prefix(self):
        result = _new_request_id("myop")
        self.assertTrue(result.startswith("myop-"))

    def test_contains_three_parts(self):
        result = _new_request_id()
        parts = result.split("-")
        self.assertGreaterEqual(len(parts), 3)

    def test_unique(self):
        a = _new_request_id()
        b = _new_request_id()
        self.assertNotEqual(a, b)

    def test_returns_string(self):
        self.assertIsInstance(_new_request_id(), str)

    def test_invalid_prefix_sanitized(self):
        # Special chars stripped; result still has valid prefix
        result = _new_request_id("my prefix!!")
        self.assertIsInstance(result, str)
        self.assertIn("-", result)


# ---------------------------------------------------------------------------
# _policy_strict_enabled
# ---------------------------------------------------------------------------

class TestPolicyStrictEnabled(unittest.TestCase):
    """Tests for _policy_strict_enabled() — OPENCLAW_POLICY_STRICT env flag."""

    def test_default_is_true(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENCLAW_POLICY_STRICT"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(_policy_strict_enabled())

    def test_zero_disables(self):
        with patch.dict(os.environ, {"OPENCLAW_POLICY_STRICT": "0"}):
            self.assertFalse(_policy_strict_enabled())

    def test_false_disables(self):
        with patch.dict(os.environ, {"OPENCLAW_POLICY_STRICT": "false"}):
            self.assertFalse(_policy_strict_enabled())

    def test_one_enables(self):
        with patch.dict(os.environ, {"OPENCLAW_POLICY_STRICT": "1"}):
            self.assertTrue(_policy_strict_enabled())

    def test_returns_bool(self):
        self.assertIsInstance(_policy_strict_enabled(), bool)


# ---------------------------------------------------------------------------
# _extract_text_from_payload
# ---------------------------------------------------------------------------

class TestExtractTextFromPayload(unittest.TestCase):
    """Tests for _extract_text_from_payload() — get text from prompt/messages."""

    def test_none_returns_empty(self):
        self.assertEqual(_extract_text_from_payload(None), "")

    def test_empty_dict_returns_empty(self):
        self.assertEqual(_extract_text_from_payload({}), "")

    def test_prompt_key_used(self):
        result = _extract_text_from_payload({"prompt": "hello world"})
        self.assertEqual(result, "hello world")

    def test_messages_joined(self):
        payload = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"},
            ]
        }
        result = _extract_text_from_payload(payload)
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_non_string_content_skipped(self):
        payload = {"messages": [{"role": "user", "content": ["list", "content"]}]}
        result = _extract_text_from_payload(payload)
        self.assertEqual(result, "")

    def test_non_dict_returns_empty(self):
        self.assertEqual(_extract_text_from_payload("just a string"), "")

    def test_returns_string(self):
        self.assertIsInstance(_extract_text_from_payload({}), str)


if __name__ == "__main__":
    unittest.main()
