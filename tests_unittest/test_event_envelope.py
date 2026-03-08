import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import event_envelope  # noqa: E402

from event_envelope import utc_now_iso, _sanitize, contains_forbidden_keys  # noqa: E402


class TestUtcNowIso(unittest.TestCase):
    """Tests for event_envelope.utc_now_iso() — UTC timestamp helper."""

    def test_returns_string(self):
        self.assertIsInstance(utc_now_iso(), str)

    def test_ends_with_z(self):
        self.assertTrue(utc_now_iso().endswith("Z"))

    def test_contains_t_separator(self):
        self.assertIn("T", utc_now_iso())

    def test_format_matches_iso(self):
        import re
        self.assertRegex(utc_now_iso(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestSanitize(unittest.TestCase):
    """Tests for event_envelope._sanitize() — recursive forbidden-key remover."""

    def test_non_dict_passthrough(self):
        self.assertEqual(_sanitize("hello"), "hello")

    def test_list_passthrough(self):
        self.assertEqual(_sanitize([1, 2, 3]), [1, 2, 3])

    def test_forbidden_key_removed(self):
        # "prompt" is a typical forbidden key
        result = _sanitize({"prompt": "secret", "ok": 1})
        self.assertNotIn("prompt", result)
        self.assertEqual(result["ok"], 1)

    def test_nested_dict_cleaned(self):
        result = _sanitize({"outer": {"prompt": "bad", "keep": "this"}})
        self.assertNotIn("prompt", result["outer"])
        self.assertEqual(result["outer"]["keep"], "this")

    def test_list_of_dicts_cleaned(self):
        result = _sanitize([{"prompt": "bad"}, {"keep": "ok"}])
        self.assertNotIn("prompt", result[0])
        self.assertIn("keep", result[1])

    def test_safe_dict_unchanged(self):
        d = {"event": "test", "severity": "info"}
        result = _sanitize(d)
        self.assertEqual(result["event"], "test")
        self.assertEqual(result["severity"], "info")

    def test_returns_dict_for_dict_input(self):
        self.assertIsInstance(_sanitize({"a": 1}), dict)


class TestContainsForbiddenKeys(unittest.TestCase):
    """Tests for event_envelope.contains_forbidden_keys()."""

    def test_clean_dict_returns_false(self):
        self.assertFalse(contains_forbidden_keys({"event": "x", "severity": "INFO"}))

    def test_forbidden_key_returns_true(self):
        self.assertTrue(contains_forbidden_keys({"prompt": "secret"}))

    def test_nested_forbidden_returns_true(self):
        self.assertTrue(contains_forbidden_keys({"outer": {"prompt": "bad"}}))

    def test_list_with_forbidden_returns_true(self):
        self.assertTrue(contains_forbidden_keys([{"prompt": "bad"}]))

    def test_empty_dict_returns_false(self):
        self.assertFalse(contains_forbidden_keys({}))

    def test_non_dict_non_list_returns_false(self):
        self.assertFalse(contains_forbidden_keys("plain string"))

    def test_returns_bool(self):
        self.assertIsInstance(contains_forbidden_keys({}), bool)


class TestEventEnvelope(unittest.TestCase):
    def test_required_keys_present(self):
        env = event_envelope.make_envelope(
            event="context_guard_triggered",
            severity="warn",
            component="policy_router",
            corr_id="req-1",
            details={"estimated_tokens": 17000},
            ts="2026-02-23T01:00:00Z",
        )
        self.assertEqual(env["schema"], event_envelope.SCHEMA_ID)
        self.assertEqual(env["event"], "context_guard_triggered")
        self.assertEqual(env["severity"], "WARN")
        self.assertEqual(env["component"], "policy_router")
        self.assertEqual(env["corr_id"], "req-1")
        self.assertIsInstance(env["details"], dict)

    def test_forbidden_keys_removed(self):
        env = event_envelope.make_envelope(
            event="x",
            severity="INFO",
            component="y",
            corr_id="z",
            details={"prompt": "secret", "nested": {"text": "hidden", "ok": 1}},
            ts="2026-02-23T01:00:00Z",
        )
        self.assertFalse(event_envelope.contains_forbidden_keys(env), env)
        self.assertEqual(env["details"]["nested"]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
