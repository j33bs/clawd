"""Tests for _routing_ids() in workspace/scripts/verify_policy_provider_aliases.py.

_routing_ids(policy) is a pure function that extracts provider IDs from a
routing policy dict. No subprocess or file I/O involved.

Covers:
- free_order entries
- intents.*.order entries
- rules[].provider entries
- Edge cases: None, empty, non-string values
"""
import importlib.util as _ilu
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "verify_policy_provider_aliases.py"

# Ensure workspace/scripts is on path for policy_router import
_scripts_dir = str(REPO_ROOT / "workspace" / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

_spec = _ilu.spec_from_file_location("verify_policy_provider_aliases_real", str(SCRIPT_PATH))
vpa = _ilu.module_from_spec(_spec)
sys.modules["verify_policy_provider_aliases_real"] = vpa
_spec.loader.exec_module(vpa)

_routing_ids = vpa._routing_ids


# ---------------------------------------------------------------------------
# _routing_ids
# ---------------------------------------------------------------------------


class TestRoutingIds(unittest.TestCase):
    """Tests for _routing_ids(policy) — extracts sorted provider ID list."""

    def test_empty_policy_returns_empty_list(self):
        self.assertEqual(_routing_ids({}), [])

    def test_none_routing_returns_empty_list(self):
        self.assertEqual(_routing_ids({"routing": None}), [])

    def test_returns_list(self):
        self.assertIsInstance(_routing_ids({}), list)

    def test_free_order_entries_included(self):
        policy = {"routing": {"free_order": ["openai", "groq"]}}
        result = _routing_ids(policy)
        self.assertIn("openai", result)
        self.assertIn("groq", result)

    def test_intent_order_entries_included(self):
        policy = {
            "routing": {
                "intents": {
                    "coding": {"order": ["anthropic", "openai"]},
                }
            }
        }
        result = _routing_ids(policy)
        self.assertIn("anthropic", result)
        self.assertIn("openai", result)

    def test_rules_provider_entries_included(self):
        policy = {
            "routing": {
                "rules": [{"provider": "minimax"}, {"provider": "groq"}]
            }
        }
        result = _routing_ids(policy)
        self.assertIn("minimax", result)
        self.assertIn("groq", result)

    def test_all_sources_combined(self):
        policy = {
            "routing": {
                "free_order": ["openai"],
                "intents": {"research": {"order": ["anthropic"]}},
                "rules": [{"provider": "groq"}],
            }
        }
        result = _routing_ids(policy)
        self.assertIn("openai", result)
        self.assertIn("anthropic", result)
        self.assertIn("groq", result)

    def test_result_is_sorted(self):
        policy = {
            "routing": {
                "free_order": ["zzz", "aaa", "mmm"],
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result, sorted(result))

    def test_duplicates_deduplicated(self):
        policy = {
            "routing": {
                "free_order": ["openai"],
                "intents": {"coding": {"order": ["openai"]}},
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result.count("openai"), 1)

    def test_non_string_free_order_entry_skipped(self):
        policy = {"routing": {"free_order": [42, None, "openai"]}}
        result = _routing_ids(policy)
        self.assertIn("openai", result)
        # Non-strings skipped
        for item in result:
            self.assertIsInstance(item, str)

    def test_non_string_rule_provider_skipped(self):
        policy = {"routing": {"rules": [{"provider": 42}, {"provider": "groq"}]}}
        result = _routing_ids(policy)
        self.assertIn("groq", result)
        for item in result:
            self.assertIsInstance(item, str)

    def test_empty_free_order_returns_empty(self):
        policy = {"routing": {"free_order": []}}
        self.assertEqual(_routing_ids(policy), [])

    def test_none_intents_handled_gracefully(self):
        policy = {"routing": {"intents": None}}
        self.assertEqual(_routing_ids(policy), [])

    def test_free_literal_included(self):
        # "free" is not excluded inside _routing_ids itself (main() skips it)
        policy = {"routing": {"free_order": ["free", "openai"]}}
        result = _routing_ids(policy)
        self.assertIn("free", result)

    def test_intent_without_order_key_skipped(self):
        policy = {
            "routing": {
                "intents": {
                    "coding": {"providers": ["openai"]},  # no "order" key
                }
            }
        }
        result = _routing_ids(policy)
        self.assertEqual(result, [])

    def test_rule_without_provider_key_skipped(self):
        policy = {"routing": {"rules": [{"model": "gpt-4"}]}}
        result = _routing_ids(policy)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
