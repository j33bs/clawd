"""Tests for pure helpers in workspace/itc_pipeline/allowlist.py.

Covers (stdlib-only, no external deps):
- _parse_ids
- is_chat_allowed (with explicit allowlist — no file I/O)
- AllowlistConfigError (exception structure)
- ChatNotAllowedError (exception structure)
- _load_allowlist_from_file
- resolve_allowlist (env-driven path)
"""
import importlib.util as _ilu
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_FILE = REPO_ROOT / "workspace" / "itc_pipeline" / "allowlist.py"

_spec = _ilu.spec_from_file_location("itc_allowlist_mod", str(ALLOWLIST_FILE))
_al = _ilu.module_from_spec(_spec)
sys.modules["itc_allowlist_mod"] = _al
_spec.loader.exec_module(_al)

_parse_ids = _al._parse_ids
_load_allowlist_from_file = _al._load_allowlist_from_file
resolve_allowlist = _al.resolve_allowlist
is_chat_allowed = _al.is_chat_allowed
AllowlistConfigError = _al.AllowlistConfigError
ChatNotAllowedError = _al.ChatNotAllowedError


# ---------------------------------------------------------------------------
# _parse_ids
# ---------------------------------------------------------------------------

class TestParseIds(unittest.TestCase):
    """Tests for _parse_ids() — parse list of strings to set of ints."""

    def test_valid_integers(self):
        allowed, invalid = _parse_ids(["123", "456", "789"], "test")
        self.assertEqual(allowed, {123, 456, 789})
        self.assertEqual(invalid, [])

    def test_non_integer_goes_to_invalid(self):
        allowed, invalid = _parse_ids(["123", "not_a_number", "456"], "test")
        self.assertIn(123, allowed)
        self.assertIn(456, allowed)
        self.assertIn("not_a_number", invalid)

    def test_empty_list_returns_empty(self):
        allowed, invalid = _parse_ids([], "test")
        self.assertEqual(allowed, set())
        self.assertEqual(invalid, [])

    def test_empty_strings_skipped(self):
        allowed, invalid = _parse_ids(["", "  ", "100"], "test")
        self.assertEqual(allowed, {100})
        self.assertEqual(invalid, [])

    def test_negative_integer_parsed(self):
        allowed, invalid = _parse_ids(["-1001234567890"], "test")
        self.assertIn(-1001234567890, allowed)
        self.assertEqual(invalid, [])

    def test_returns_set_and_list(self):
        allowed, invalid = _parse_ids(["1", "2"], "test")
        self.assertIsInstance(allowed, set)
        self.assertIsInstance(invalid, list)

    def test_mixed_valid_invalid(self):
        allowed, invalid = _parse_ids(["1", "two", "3"], "test")
        self.assertEqual(len(allowed), 2)
        self.assertEqual(len(invalid), 1)


# ---------------------------------------------------------------------------
# AllowlistConfigError
# ---------------------------------------------------------------------------

class TestAllowlistConfigError(unittest.TestCase):
    """Tests for AllowlistConfigError exception class."""

    def test_is_runtime_error(self):
        err = AllowlistConfigError("missing config")
        self.assertIsInstance(err, RuntimeError)

    def test_default_reason_code(self):
        err = AllowlistConfigError("missing config")
        self.assertEqual(err.reason_code, "telegram_not_configured")

    def test_custom_reason_code(self):
        err = AllowlistConfigError("bad ids", reason_code="invalid_data")
        self.assertEqual(err.reason_code, "invalid_data")

    def test_message_contains_reason(self):
        err = AllowlistConfigError("problem here")
        self.assertIn("telegram_not_configured", str(err))

    def test_message_contains_detail(self):
        err = AllowlistConfigError("problem here")
        self.assertIn("problem here", str(err))


# ---------------------------------------------------------------------------
# ChatNotAllowedError
# ---------------------------------------------------------------------------

class TestChatNotAllowedError(unittest.TestCase):
    """Tests for ChatNotAllowedError exception class."""

    def test_is_runtime_error(self):
        err = ChatNotAllowedError(12345)
        self.assertIsInstance(err, RuntimeError)

    def test_reason_code(self):
        err = ChatNotAllowedError(12345)
        self.assertEqual(err.reason_code, "telegram_chat_not_allowed")

    def test_chat_id_stored(self):
        err = ChatNotAllowedError(99999)
        self.assertEqual(err.chat_id, 99999)

    def test_chat_title_stored(self):
        err = ChatNotAllowedError(123, chat_title="My Chat")
        self.assertEqual(err.chat_title, "My Chat")

    def test_message_contains_chat_id(self):
        err = ChatNotAllowedError(-1001234567890)
        self.assertIn("-1001234567890", str(err))


# ---------------------------------------------------------------------------
# _load_allowlist_from_file
# ---------------------------------------------------------------------------

class TestLoadAllowlistFromFile(unittest.TestCase):
    """Tests for _load_allowlist_from_file() — JSON allowlist loader."""

    def test_missing_file_returns_empty(self):
        allowed, invalid, source, warnings = _load_allowlist_from_file(Path("/nonexistent/path.json"))
        self.assertEqual(allowed, set())
        self.assertEqual(source, "missing")

    def test_allow_chat_ids_key_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "allowlist.json"
            p.write_text(json.dumps({"allow_chat_ids": [111, 222, 333]}), encoding="utf-8")
            allowed, invalid, source, warnings = _load_allowlist_from_file(p)
            self.assertIn(111, allowed)
            self.assertIn(222, allowed)
            self.assertEqual(source, "allow_chat_ids")

    def test_legacy_allowfrom_key_warns(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "allowlist.json"
            p.write_text(json.dumps({"allowFrom": [444, 555]}), encoding="utf-8")
            allowed, invalid, source, warnings = _load_allowlist_from_file(p)
            self.assertIn(444, allowed)
            self.assertEqual(source, "allowFrom")
            self.assertTrue(any("Legacy" in w for w in warnings))

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "allowlist.json"
            p.write_text("NOT JSON", encoding="utf-8")
            with self.assertRaises(AllowlistConfigError):
                _load_allowlist_from_file(p)

    def test_empty_json_object_returns_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "allowlist.json"
            p.write_text(json.dumps({}), encoding="utf-8")
            allowed, invalid, source, warnings = _load_allowlist_from_file(p)
            self.assertEqual(allowed, set())
            self.assertEqual(source, "missing")


# ---------------------------------------------------------------------------
# is_chat_allowed (with explicit allowlist — no file I/O)
# ---------------------------------------------------------------------------

class TestIsChatAllowed(unittest.TestCase):
    """Tests for is_chat_allowed() with explicit allowlist parameter."""

    def test_allowed_chat_returns_true(self):
        result = is_chat_allowed(100, allowlist={100, 200, 300})
        self.assertTrue(result)

    def test_not_in_allowlist_returns_false(self):
        result = is_chat_allowed(999, allowlist={100, 200})
        self.assertFalse(result)

    def test_excluded_title_returns_false(self):
        # Title containing "responder" should be excluded
        result = is_chat_allowed(100, chat_title="BotResponder", allowlist={100})
        self.assertFalse(result)

    def test_botfather_excluded(self):
        result = is_chat_allowed(100, chat_title="BotFather", allowlist={100})
        self.assertFalse(result)

    def test_normal_title_not_excluded(self):
        result = is_chat_allowed(100, chat_title="My Normal Chat", allowlist={100})
        self.assertTrue(result)

    def test_empty_allowlist_returns_false(self):
        result = is_chat_allowed(100, allowlist=set())
        self.assertFalse(result)

    def test_returns_bool(self):
        result = is_chat_allowed(1, allowlist={1})
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# resolve_allowlist (env-driven)
# ---------------------------------------------------------------------------

class TestResolveAllowlist(unittest.TestCase):
    """Tests for resolve_allowlist() — env var → allowlist resolution."""

    def test_env_var_used_when_set(self):
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": "111,222,333"}):
            allowed, source, invalid, warnings = resolve_allowlist()
            self.assertIn(111, allowed)
            self.assertIn(222, allowed)
            self.assertEqual(source, "env")

    def test_env_var_invalid_entries(self):
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": "111,bad,222"}):
            allowed, source, invalid, warnings = resolve_allowlist()
            self.assertIn("bad", invalid)

    def test_returns_tuple_of_four(self):
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": "999"}):
            result = resolve_allowlist()
            self.assertEqual(len(result), 4)


if __name__ == "__main__":
    unittest.main()
