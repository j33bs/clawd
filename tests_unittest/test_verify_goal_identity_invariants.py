"""Tests for scripts.verify_goal_identity_invariants — walk_strings pure function."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "workspace" / "scripts" / "verify_goal_identity_invariants.py"


def _load_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify_goal_identity_invariants", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestWalkStrings(unittest.TestCase):
    """Tests for walk_strings(obj) — recursive string extractor."""

    def setUp(self):
        self.mod = _load_mod()

    def _collect(self, obj) -> list:
        return list(self.mod.walk_strings(obj))

    def test_string_yields_itself(self):
        self.assertEqual(self._collect("hello"), ["hello"])

    def test_list_of_strings(self):
        result = self._collect(["a", "b", "c"])
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)

    def test_dict_yields_keys_and_values(self):
        result = self._collect({"key": "value"})
        self.assertIn("key", result)
        self.assertIn("value", result)

    def test_nested_dict(self):
        result = self._collect({"outer": {"inner": "deep"}})
        self.assertIn("outer", result)
        self.assertIn("inner", result)
        self.assertIn("deep", result)

    def test_mixed_list(self):
        result = self._collect(["string", 42, None, "other"])
        self.assertIn("string", result)
        self.assertIn("other", result)
        # Non-strings are skipped
        self.assertNotIn(42, result)

    def test_empty_string_yielded(self):
        result = self._collect("")
        self.assertIn("", result)

    def test_empty_list_returns_empty(self):
        self.assertEqual(self._collect([]), [])

    def test_empty_dict_returns_empty(self):
        self.assertEqual(self._collect({}), [])

    def test_nested_list_of_dicts(self):
        obj = [{"k": "v"}, {"k2": "v2"}]
        result = self._collect(obj)
        self.assertIn("k", result)
        self.assertIn("v", result)
        self.assertIn("k2", result)
        self.assertIn("v2", result)

    def test_integer_obj_returns_empty(self):
        # Non-string, non-list, non-dict skips
        self.assertEqual(self._collect(42), [])

    def test_deeply_nested(self):
        obj = {"a": {"b": {"c": "leaf"}}}
        result = self._collect(obj)
        self.assertIn("leaf", result)

    def test_returns_generator(self):
        import types
        result = self.mod.walk_strings("hello")
        self.assertIsInstance(result, types.GeneratorType)


if __name__ == "__main__":
    unittest.main()
