"""Tests for pure helper functions in workspace/scripts/policy_router.py.

Covers (no network, no file I/O):
- normalize_provider_id
- denormalize_provider_ids
- canonical_intent
- _normalize_provider_order
- _deep_merge
- _redact_text / _redact_detail
- _outcome_class_from_reason
- _budget_intent_key
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import policy_router as _pr  # noqa: E402

normalize_provider_id = _pr.normalize_provider_id
denormalize_provider_ids = _pr.denormalize_provider_ids
canonical_intent = _pr.canonical_intent
_normalize_provider_order = _pr._normalize_provider_order
_deep_merge = _pr._deep_merge
_redact_text = _pr._redact_text
_redact_detail = _pr._redact_detail
_outcome_class_from_reason = _pr._outcome_class_from_reason
_budget_intent_key = _pr._budget_intent_key


# ---------------------------------------------------------------------------
# normalize_provider_id
# ---------------------------------------------------------------------------

class TestNormalizeProviderId(unittest.TestCase):
    """Tests for normalize_provider_id() — alias resolution."""

    def test_known_alias_resolved(self):
        self.assertEqual(normalize_provider_id("qwen-portal"), "qwen_alibaba")

    def test_unknown_id_passthrough(self):
        self.assertEqual(normalize_provider_id("my-custom-provider"), "my-custom-provider")

    def test_non_string_passthrough(self):
        self.assertIsNone(normalize_provider_id(None))
        self.assertEqual(normalize_provider_id(42), 42)

    def test_strips_whitespace(self):
        # Stripping happens before alias lookup; whitespace-padded known key
        result = normalize_provider_id("  groq  ")
        self.assertEqual(result, "groq")

    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_provider_id(""), "")

    def test_groq_identity(self):
        self.assertEqual(normalize_provider_id("groq"), "groq")

    def test_google_gemini_cli_identity(self):
        self.assertEqual(normalize_provider_id("google-gemini-cli"), "google-gemini-cli")


# ---------------------------------------------------------------------------
# denormalize_provider_ids
# ---------------------------------------------------------------------------

class TestDenormalizeProviderIds(unittest.TestCase):
    """Tests for denormalize_provider_ids() — reverse alias lookup."""

    def test_aliased_norm_returns_raw_keys(self):
        result = denormalize_provider_ids("qwen_alibaba")
        # "qwen-portal" and "qwen_alibaba" both map to "qwen_alibaba"
        self.assertIn("qwen-portal", result)

    def test_unknown_norm_returns_empty(self):
        self.assertEqual(denormalize_provider_ids("nonexistent_norm"), [])

    def test_returns_list(self):
        self.assertIsInstance(denormalize_provider_ids("groq"), list)

    def test_groq_maps_to_itself(self):
        result = denormalize_provider_ids("groq")
        self.assertIn("groq", result)


# ---------------------------------------------------------------------------
# canonical_intent
# ---------------------------------------------------------------------------

class TestCanonicalIntent(unittest.TestCase):
    """Tests for canonical_intent() — teamchat: → coding, else passthrough."""

    def test_teamchat_prefix_becomes_coding(self):
        self.assertEqual(canonical_intent("teamchat:debug"), "coding")

    def test_teamchat_bare_becomes_coding(self):
        self.assertEqual(canonical_intent("teamchat:"), "coding")

    def test_non_teamchat_unchanged(self):
        self.assertEqual(canonical_intent("governance"), "governance")

    def test_none_becomes_empty_string(self):
        self.assertEqual(canonical_intent(None), "")

    def test_empty_string_unchanged(self):
        self.assertEqual(canonical_intent(""), "")

    def test_returns_string(self):
        self.assertIsInstance(canonical_intent("any"), str)


# ---------------------------------------------------------------------------
# _normalize_provider_order
# ---------------------------------------------------------------------------

class TestNormalizeProviderOrder(unittest.TestCase):
    """Tests for _normalize_provider_order() — list of strings → normalized IDs."""

    def test_empty_list_returns_empty(self):
        self.assertEqual(_normalize_provider_order([]), [])

    def test_non_list_returns_empty(self):
        self.assertEqual(_normalize_provider_order(None), [])
        self.assertEqual(_normalize_provider_order("groq"), [])

    def test_aliases_applied(self):
        result = _normalize_provider_order(["qwen-portal", "groq"])
        self.assertEqual(result[0], "qwen_alibaba")
        self.assertEqual(result[1], "groq")

    def test_non_string_items_skipped(self):
        result = _normalize_provider_order(["groq", 42, None, "ollama"])
        self.assertEqual(result, ["groq", "ollama"])

    def test_returns_list(self):
        self.assertIsInstance(_normalize_provider_order(["groq"]), list)


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge(unittest.TestCase):
    """Tests for _deep_merge() — recursive dict merge with defaults."""

    def test_incoming_overrides_default(self):
        result = _deep_merge({"a": 1}, {"a": 2})
        self.assertEqual(result["a"], 2)

    def test_missing_incoming_uses_default(self):
        result = _deep_merge({"a": 1, "b": 2}, {"a": 99})
        self.assertEqual(result["b"], 2)

    def test_new_incoming_key_added(self):
        result = _deep_merge({"a": 1}, {"b": 2})
        self.assertIn("b", result)

    def test_nested_merge(self):
        defaults = {"x": {"a": 1, "b": 2}}
        incoming = {"x": {"a": 99}}
        result = _deep_merge(defaults, incoming)
        self.assertEqual(result["x"]["a"], 99)
        self.assertEqual(result["x"]["b"], 2)

    def test_non_dict_defaults_returns_incoming(self):
        result = _deep_merge("default", "incoming")
        self.assertEqual(result, "incoming")

    def test_non_dict_incoming_with_none_returns_default(self):
        result = _deep_merge("default", None)
        self.assertEqual(result, "default")

    def test_returns_dict(self):
        self.assertIsInstance(_deep_merge({}, {}), dict)


# ---------------------------------------------------------------------------
# _redact_text
# ---------------------------------------------------------------------------

class TestRedactText(unittest.TestCase):
    """Tests for _redact_text() — secrets redaction in strings."""

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc123"
        result = _redact_text(text)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", result)
        self.assertIn("<redacted", result)

    def test_api_key_value_redacted(self):
        text = "api_key=sk-ant-abcdef12345678"
        result = _redact_text(text)
        self.assertNotIn("sk-ant-abcdef12345678", result)

    def test_sk_prefix_token_redacted(self):
        result = _redact_text("token sk-api12345678901234")
        self.assertIn("<redacted", result)

    def test_no_secrets_unchanged(self):
        text = "hello world no secrets"
        result = _redact_text(text)
        self.assertIn("hello world", result)

    def test_returns_string(self):
        self.assertIsInstance(_redact_text("anything"), str)

    def test_empty_string(self):
        self.assertEqual(_redact_text(""), "")


# ---------------------------------------------------------------------------
# _redact_detail
# ---------------------------------------------------------------------------

class TestRedactDetail(unittest.TestCase):
    """Tests for _redact_detail() — recursive dict/list redaction."""

    def test_string_input_redacts_secrets(self):
        result = _redact_detail("Bearer sk-abc123456789012")
        self.assertNotIn("sk-abc123456789012", str(result))

    def test_none_returns_none(self):
        self.assertIsNone(_redact_detail(None))

    def test_list_recursed(self):
        result = _redact_detail(["hello", "api_key=secret123"])
        self.assertIsInstance(result, list)

    def test_dict_sensitive_key_redacted(self):
        result = _redact_detail({"authorization": "Bearer tok123456789"})
        self.assertEqual(result["authorization"], "<redacted>")

    def test_dict_safe_key_preserved(self):
        result = _redact_detail({"message": "hello world"})
        self.assertEqual(result["message"], "hello world")

    def test_numeric_passthrough(self):
        self.assertEqual(_redact_detail(42), 42)


# ---------------------------------------------------------------------------
# _outcome_class_from_reason
# ---------------------------------------------------------------------------

class TestOutcomeClassFromReason(unittest.TestCase):
    """Tests for _outcome_class_from_reason() — reason code → class."""

    def test_success(self):
        self.assertEqual(_outcome_class_from_reason("success"), "success")

    def test_ok(self):
        self.assertEqual(_outcome_class_from_reason("ok"), "success")

    def test_timeout(self):
        self.assertEqual(_outcome_class_from_reason("timeout_error"), "timeout")

    def test_rate_limit_429(self):
        self.assertEqual(_outcome_class_from_reason("429"), "rate_limit")

    def test_rate_in_code(self):
        self.assertEqual(_outcome_class_from_reason("rate_exceeded"), "rate_limit")

    def test_auth_error(self):
        self.assertEqual(_outcome_class_from_reason("auth_failure"), "auth_error")

    def test_missing_api_key(self):
        self.assertEqual(_outcome_class_from_reason("missing_api_key"), "auth_error")

    def test_circuit_open(self):
        self.assertEqual(_outcome_class_from_reason("circuit_open"), "circuit_open")

    def test_unknown_is_failure(self):
        self.assertEqual(_outcome_class_from_reason("weird_error"), "failure")

    def test_none_is_failure(self):
        self.assertEqual(_outcome_class_from_reason(None), "failure")


# ---------------------------------------------------------------------------
# _budget_intent_key
# ---------------------------------------------------------------------------

class TestBudgetIntentKey(unittest.TestCase):
    """Tests for _budget_intent_key() — teamchat: → coding for budget keys."""

    def test_teamchat_prefix_returns_coding(self):
        self.assertEqual(_budget_intent_key("teamchat:session"), "coding")

    def test_non_teamchat_unchanged(self):
        self.assertEqual(_budget_intent_key("governance"), "governance")

    def test_none_passthrough(self):
        self.assertIsNone(_budget_intent_key(None))

    def test_empty_string_passthrough(self):
        self.assertEqual(_budget_intent_key(""), "")

    def test_returns_original_type_for_non_string(self):
        self.assertEqual(_budget_intent_key(42), 42)


if __name__ == "__main__":
    unittest.main()
