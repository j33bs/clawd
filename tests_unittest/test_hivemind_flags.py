"""Tests for hivemind.flags — is_enabled, any_enabled, enabled_map."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.flags import is_enabled, any_enabled, enabled_map, TRUTHY_VALUES


class TestIsEnabled(unittest.TestCase):
    """Tests for is_enabled() — env var truthy check."""

    def _env(self, **kwargs):
        return {k: str(v) for k, v in kwargs.items()}

    def test_missing_key_returns_false(self):
        self.assertFalse(is_enabled("ENABLE_MISSING_FLAG", environ={}))

    def test_zero_returns_false(self):
        self.assertFalse(is_enabled("F", environ={"F": "0"}))

    def test_false_string_returns_false(self):
        self.assertFalse(is_enabled("F", environ={"F": "false"}))

    def test_empty_string_returns_false(self):
        self.assertFalse(is_enabled("F", environ={"F": ""}))

    def test_one_returns_true(self):
        self.assertTrue(is_enabled("F", environ={"F": "1"}))

    def test_true_string_returns_true(self):
        self.assertTrue(is_enabled("F", environ={"F": "true"}))

    def test_yes_returns_true(self):
        self.assertTrue(is_enabled("F", environ={"F": "yes"}))

    def test_on_returns_true(self):
        self.assertTrue(is_enabled("F", environ={"F": "on"}))

    def test_case_insensitive_true(self):
        self.assertTrue(is_enabled("F", environ={"F": "TRUE"}))
        self.assertTrue(is_enabled("F", environ={"F": "Yes"}))
        self.assertTrue(is_enabled("F", environ={"F": "ON"}))

    def test_whitespace_stripped(self):
        self.assertTrue(is_enabled("F", environ={"F": "  1  "}))

    def test_arbitrary_text_returns_false(self):
        self.assertFalse(is_enabled("F", environ={"F": "enabled"}))

    def test_none_environ_uses_os_environ(self):
        # Just check it doesn't crash when environ=None
        result = is_enabled("ENABLE_TOTALLY_NONEXISTENT_FLAG_12345", environ=None)
        self.assertFalse(result)


class TestAnyEnabled(unittest.TestCase):
    """Tests for any_enabled() — OR over multiple flags."""

    def test_empty_names_returns_false(self):
        self.assertFalse(any_enabled([], environ={}))

    def test_all_disabled_returns_false(self):
        env = {"A": "0", "B": "0", "C": "0"}
        self.assertFalse(any_enabled(["A", "B", "C"], environ=env))

    def test_one_enabled_returns_true(self):
        env = {"A": "0", "B": "1", "C": "0"}
        self.assertTrue(any_enabled(["A", "B", "C"], environ=env))

    def test_all_enabled_returns_true(self):
        env = {"A": "1", "B": "1"}
        self.assertTrue(any_enabled(["A", "B"], environ=env))

    def test_single_flag_enabled(self):
        self.assertTrue(any_enabled(["F"], environ={"F": "1"}))

    def test_single_flag_disabled(self):
        self.assertFalse(any_enabled(["F"], environ={"F": "0"}))

    def test_short_circuits_on_first_true(self):
        # Only checks until True found; we can't test short-circuit directly,
        # but we verify the result is correct regardless of ordering.
        env = {"A": "1", "B": "1", "C": "1"}
        self.assertTrue(any_enabled(["C", "B", "A"], environ=env))


class TestEnabledMap(unittest.TestCase):
    """Tests for enabled_map() — dict of flag → bool."""

    def test_empty_names_returns_empty(self):
        result = enabled_map([], environ={})
        self.assertEqual(result, {})

    def test_all_disabled(self):
        env = {"A": "0", "B": "false"}
        result = enabled_map(["A", "B"], environ=env)
        self.assertEqual(result, {"A": False, "B": False})

    def test_all_enabled(self):
        env = {"A": "1", "B": "yes"}
        result = enabled_map(["A", "B"], environ=env)
        self.assertEqual(result, {"A": True, "B": True})

    def test_mixed_flags(self):
        env = {"A": "1", "B": "0", "C": "true"}
        result = enabled_map(["A", "B", "C"], environ=env)
        self.assertTrue(result["A"])
        self.assertFalse(result["B"])
        self.assertTrue(result["C"])

    def test_missing_flag_is_false(self):
        result = enabled_map(["MISSING_FLAG"], environ={})
        self.assertFalse(result["MISSING_FLAG"])

    def test_keys_are_strings(self):
        result = enabled_map(["FLAG"], environ={"FLAG": "1"})
        for k in result:
            self.assertIsInstance(k, str)


class TestTruthyValues(unittest.TestCase):
    """Tests for TRUTHY_VALUES — canonical set of truthy strings."""

    def test_contains_one(self):
        self.assertIn("1", TRUTHY_VALUES)

    def test_contains_true(self):
        self.assertIn("true", TRUTHY_VALUES)

    def test_contains_yes(self):
        self.assertIn("yes", TRUTHY_VALUES)

    def test_contains_on(self):
        self.assertIn("on", TRUTHY_VALUES)

    def test_does_not_contain_false(self):
        self.assertNotIn("false", TRUTHY_VALUES)

    def test_does_not_contain_zero(self):
        self.assertNotIn("0", TRUTHY_VALUES)

    def test_is_set(self):
        self.assertIsInstance(TRUTHY_VALUES, (set, frozenset))


if __name__ == "__main__":
    unittest.main()
