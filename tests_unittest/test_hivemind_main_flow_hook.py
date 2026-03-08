"""Tests for hivemind.integrations.main_flow_hook pure helper functions."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.integrations.main_flow_hook import (  # noqa: E402
    _unique,
    _sorted_unique,
    _read_json,
    _expand_policy_order,
    _resolve_from_runtime_catalog,
    stable_seed,
    dynamics_flags_enabled,
)


class TestUnique(unittest.TestCase):
    """Tests for _unique() — order-preserving dedup."""

    def test_empty_returns_empty(self):
        self.assertEqual(_unique([]), [])

    def test_no_duplicates_preserved(self):
        self.assertEqual(_unique(["a", "b", "c"]), ["a", "b", "c"])

    def test_duplicates_removed_first_kept(self):
        self.assertEqual(_unique(["a", "b", "a"]), ["a", "b"])

    def test_whitespace_stripped(self):
        result = _unique(["  a  ", "b"])
        self.assertIn("a", result)

    def test_empty_strings_excluded(self):
        result = _unique(["", "b", ""])
        self.assertNotIn("", result)
        self.assertIn("b", result)

    def test_order_preserved(self):
        result = _unique(["b", "a", "c"])
        self.assertEqual(result, ["b", "a", "c"])

    def test_returns_list(self):
        self.assertIsInstance(_unique(["x"]), list)


class TestSortedUnique(unittest.TestCase):
    """Tests for _sorted_unique() — sorted dedup."""

    def test_empty_returns_empty(self):
        self.assertEqual(_sorted_unique([]), [])

    def test_sorts_output(self):
        self.assertEqual(_sorted_unique(["b", "a", "c"]), ["a", "b", "c"])

    def test_deduplicates(self):
        self.assertEqual(_sorted_unique(["b", "a", "b"]), ["a", "b"])

    def test_returns_list(self):
        self.assertIsInstance(_sorted_unique(["x"]), list)


class TestReadJson(unittest.TestCase):
    """Tests for _read_json() — JSON file loader with error handling."""

    def test_valid_json_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.json"
            p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
            result = _read_json(p)
            self.assertEqual(result, {"key": "value"})

    def test_missing_file_returns_empty(self):
        result = _read_json(Path("/nonexistent/totally/missing.json"))
        self.assertEqual(result, {})

    def test_invalid_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text("not valid json {{{{", encoding="utf-8")
            result = _read_json(p)
            self.assertEqual(result, {})

    def test_json_list_returns_empty(self):
        # A JSON array is not a dict — should return {}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "list.json"
            p.write_text("[1, 2, 3]", encoding="utf-8")
            result = _read_json(p)
            self.assertEqual(result, {})

    def test_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.json"
            p.write_text("{}", encoding="utf-8")
            result = _read_json(p)
            self.assertIsInstance(result, dict)


class TestExpandPolicyOrder(unittest.TestCase):
    """Tests for _expand_policy_order() — expand 'free' keyword in routing order."""

    def _policy(self, free_order):
        return {"routing": {"free_order": free_order}}

    def test_empty_order_returns_empty(self):
        result = _expand_policy_order(self._policy(["a"]), [])
        self.assertEqual(result, [])

    def test_literal_names_passed_through(self):
        result = _expand_policy_order(self._policy([]), ["gpt", "local"])
        self.assertEqual(result, ["gpt", "local"])

    def test_free_expands_to_free_order(self):
        result = _expand_policy_order(self._policy(["gemini", "local"]), ["free"])
        self.assertEqual(result, ["gemini", "local"])

    def test_mixed_free_and_literal(self):
        result = _expand_policy_order(self._policy(["gemini"]), ["gpt", "free"])
        self.assertEqual(result, ["gpt", "gemini"])

    def test_deduplicates_output(self):
        result = _expand_policy_order(self._policy(["gpt"]), ["gpt", "free"])
        self.assertEqual(result.count("gpt"), 1)

    def test_non_mapping_policy_returns_empty(self):
        result = _expand_policy_order(None, ["free", "gpt"])  # type: ignore[arg-type]
        self.assertIsInstance(result, list)

    def test_returns_list(self):
        result = _expand_policy_order(self._policy([]), ["a"])
        self.assertIsInstance(result, list)


class TestResolveFromRuntimeCatalog(unittest.TestCase):
    """Tests for _resolve_from_runtime_catalog() — candidates + policy provider merge."""

    def test_candidates_only(self):
        result = _resolve_from_runtime_catalog(
            policy=None,
            context=None,
            candidates=["codex", "gpt"],
        )
        self.assertIn("codex", result)
        self.assertIn("gpt", result)

    def test_no_candidates_no_policy_returns_empty(self):
        result = _resolve_from_runtime_catalog(policy=None, context=None, candidates=None)
        self.assertEqual(result, [])

    def test_policy_providers_included(self):
        policy = {"providers": {"gemini": {}, "local": {}}}
        result = _resolve_from_runtime_catalog(
            policy=policy,
            context=None,
            candidates=None,
        )
        self.assertIn("gemini", result)
        self.assertIn("local", result)

    def test_deduplicates_across_sources(self):
        policy = {"providers": {"gpt": {}}}
        result = _resolve_from_runtime_catalog(
            policy=policy,
            context=None,
            candidates=["gpt"],
        )
        self.assertEqual(result.count("gpt"), 1)

    def test_returns_list(self):
        result = _resolve_from_runtime_catalog(policy=None, context=None, candidates=["a"])
        self.assertIsInstance(result, list)


class TestStableSeed(unittest.TestCase):
    """Tests for stable_seed() — deterministic int from agent IDs + session."""

    def test_returns_int(self):
        self.assertIsInstance(stable_seed(["a", "b"]), int)

    def test_deterministic(self):
        self.assertEqual(stable_seed(["a", "b"]), stable_seed(["a", "b"]))

    def test_order_invariant(self):
        # sorted internally, so ["b", "a"] == ["a", "b"]
        self.assertEqual(stable_seed(["b", "a"]), stable_seed(["a", "b"]))

    def test_session_id_changes_seed(self):
        without = stable_seed(["a", "b"])
        with_session = stable_seed(["a", "b"], session_id="sess-1")
        self.assertNotEqual(without, with_session)

    def test_different_ids_different_seeds(self):
        self.assertNotEqual(stable_seed(["x"]), stable_seed(["y"]))

    def test_session_id_deterministic(self):
        s1 = stable_seed(["a", "b"], session_id="sess-1")
        s2 = stable_seed(["a", "b"], session_id="sess-1")
        self.assertEqual(s1, s2)

    def test_none_session_same_as_no_session(self):
        self.assertEqual(stable_seed(["a"], session_id=None), stable_seed(["a"]))


class TestDynamicsFlagsEnabled(unittest.TestCase):
    """Tests for dynamics_flags_enabled() — any TACTI flag set."""

    def test_all_off_returns_false(self):
        env = {
            "ENABLE_MURMURATION": "0",
            "ENABLE_RESERVOIR": "0",
            "ENABLE_PHYSARUM_ROUTER": "0",
            "ENABLE_TRAIL_MEMORY": "0",
        }
        self.assertFalse(dynamics_flags_enabled(environ=env))

    def test_one_on_returns_true(self):
        env = {
            "ENABLE_MURMURATION": "1",
            "ENABLE_RESERVOIR": "0",
            "ENABLE_PHYSARUM_ROUTER": "0",
            "ENABLE_TRAIL_MEMORY": "0",
        }
        self.assertTrue(dynamics_flags_enabled(environ=env))

    def test_all_on_returns_true(self):
        env = {
            "ENABLE_MURMURATION": "1",
            "ENABLE_RESERVOIR": "1",
            "ENABLE_PHYSARUM_ROUTER": "1",
            "ENABLE_TRAIL_MEMORY": "1",
        }
        self.assertTrue(dynamics_flags_enabled(environ=env))

    def test_empty_environ_returns_false(self):
        self.assertFalse(dynamics_flags_enabled(environ={}))

    def test_returns_bool(self):
        self.assertIsInstance(dynamics_flags_enabled(environ={}), bool)


if __name__ == "__main__":
    unittest.main()
