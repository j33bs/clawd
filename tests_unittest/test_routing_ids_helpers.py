"""Tests for _routing_ids() in workspace/scripts/verify_policy_provider_aliases.py.

Pure helper — extracts sorted provider IDs from a routing policy dict.
Stubs policy_router to avoid importing the real module.
"""
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Stub policy_router so the top-level import in the script doesn't fail
_pr_mod = types.ModuleType("policy_router")
_pr_mod.normalize_provider_id = lambda x: x  # identity for isolation
sys.modules.setdefault("policy_router", _pr_mod)

# The script does sys.path manipulation and then imports policy_router at
# module level.  We load it via importlib after the stub is in place.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "verify_policy_provider_aliases",
    str(REPO_ROOT / "workspace" / "scripts" / "verify_policy_provider_aliases.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_routing_ids = _mod._routing_ids


class TestRoutingIds(unittest.TestCase):
    """Tests for _routing_ids(policy)."""

    def test_empty_policy_returns_empty(self):
        result = _routing_ids({})
        self.assertEqual(result, [])

    def test_free_order_string_entries(self):
        policy = {"routing": {"free_order": ["openai", "anthropic"]}}
        result = _routing_ids(policy)
        self.assertEqual(result, ["anthropic", "openai"])  # sorted

    def test_free_order_non_string_entries_skipped(self):
        policy = {"routing": {"free_order": [{"nested": "dict"}, 42, "groq"]}}
        result = _routing_ids(policy)
        self.assertEqual(result, ["groq"])

    def test_intents_order_entries(self):
        policy = {
            "routing": {
                "intents": {
                    "governance": {"order": ["local", "anthropic"]},
                    "search": {"order": ["openai"]},
                }
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result, sorted(["local", "anthropic", "openai"]))

    def test_rules_provider_entries(self):
        policy = {
            "routing": {
                "rules": [
                    {"provider": "grok", "condition": "something"},
                    {"provider": "gemini"},
                ]
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result, ["gemini", "grok"])

    def test_deduplication_across_sources(self):
        policy = {
            "routing": {
                "free_order": ["openai"],
                "intents": {"chat": {"order": ["openai", "anthropic"]}},
                "rules": [{"provider": "anthropic"}],
            }
        }
        result = _routing_ids(policy)
        # "openai" and "anthropic" each appear once
        self.assertEqual(result, ["anthropic", "openai"])

    def test_result_is_sorted(self):
        policy = {
            "routing": {
                "free_order": ["zzz", "aaa", "mmm"],
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result, sorted(result))

    def test_none_routing_value_handled(self):
        # routing key exists but value is None — uses {} fallback via `or {}`
        policy = {"routing": None}
        result = _routing_ids(policy)
        self.assertEqual(result, [])

    def test_rules_non_dict_entry_skipped(self):
        policy = {"routing": {"rules": ["not-a-dict", {"provider": "valid"}]}}
        result = _routing_ids(policy)
        self.assertEqual(result, ["valid"])

    def test_intents_non_string_order_skipped(self):
        policy = {
            "routing": {
                "intents": {
                    "chat": {"order": [42, None, "anthropic"]},
                }
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result, ["anthropic"])

    def test_returns_list(self):
        result = _routing_ids({})
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
