"""Tests for workspace/itc_pipeline/allowlist.py pure helper functions.

Covers (no network, no actual Telegram credentials):
- _parse_ids
- _load_allowlist_from_file
- resolve_allowlist (env var path)
- is_chat_allowed (with explicit allowlist)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
ITC_DIR = REPO_ROOT / "workspace" / "itc_pipeline"
if str(ITC_DIR) not in sys.path:
    sys.path.insert(0, str(ITC_DIR))

from allowlist import (  # noqa: E402
    AllowlistConfigError,
    ChatNotAllowedError,
    _load_allowlist_from_file,
    _parse_ids,
    is_chat_allowed,
    resolve_allowlist,
)


# ---------------------------------------------------------------------------
# _parse_ids
# ---------------------------------------------------------------------------

class TestParseIds(unittest.TestCase):
    """Tests for _parse_ids() — string list → (set[int], list[str])."""

    def test_valid_integers(self):
        ids, invalid = _parse_ids(["123", "456"], "test")
        self.assertIn(123, ids)
        self.assertIn(456, ids)
        self.assertEqual(invalid, [])

    def test_invalid_returns_in_list(self):
        ids, invalid = _parse_ids(["abc"], "test")
        self.assertEqual(len(ids), 0)
        self.assertIn("abc", invalid)

    def test_mixed_valid_and_invalid(self):
        ids, invalid = _parse_ids(["100", "bad", "200"], "test")
        self.assertIn(100, ids)
        self.assertIn(200, ids)
        self.assertIn("bad", invalid)

    def test_empty_string_skipped(self):
        ids, invalid = _parse_ids(["", "   ", "100"], "test")
        self.assertIn(100, ids)
        self.assertEqual(invalid, [])

    def test_negative_int_valid(self):
        ids, invalid = _parse_ids(["-1001234567890"], "test")
        self.assertIn(-1001234567890, ids)
        self.assertEqual(invalid, [])

    def test_empty_list(self):
        ids, invalid = _parse_ids([], "test")
        self.assertEqual(ids, set())
        self.assertEqual(invalid, [])

    def test_returns_set_and_list(self):
        ids, invalid = _parse_ids(["1"], "test")
        self.assertIsInstance(ids, set)
        self.assertIsInstance(invalid, list)


# ---------------------------------------------------------------------------
# _load_allowlist_from_file
# ---------------------------------------------------------------------------

class TestLoadAllowlistFromFile(unittest.TestCase):
    """Tests for _load_allowlist_from_file() — JSON file loading."""

    def test_missing_file_returns_empty(self):
        result = _load_allowlist_from_file(Path("/nonexistent/path/file.json"))
        ids, invalid, source, warnings = result
        self.assertEqual(ids, set())
        self.assertEqual(source, "missing")

    def test_allow_chat_ids_key_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "allow.json"
            path.write_text(json.dumps({"allow_chat_ids": [111, 222]}), encoding="utf-8")
            ids, invalid, source, warnings = _load_allowlist_from_file(path)
            self.assertIn(111, ids)
            self.assertIn(222, ids)
            self.assertEqual(source, "allow_chat_ids")

    def test_legacy_allow_from_key_triggers_warning(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "allow.json"
            path.write_text(json.dumps({"allowFrom": [333]}), encoding="utf-8")
            ids, invalid, source, warnings = _load_allowlist_from_file(path)
            self.assertIn(333, ids)
            self.assertEqual(source, "allowFrom")
            self.assertTrue(len(warnings) > 0)

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text("NOT JSON", encoding="utf-8")
            with self.assertRaises(AllowlistConfigError):
                _load_allowlist_from_file(path)

    def test_no_known_key_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "allow.json"
            path.write_text(json.dumps({"some_other_key": [1, 2]}), encoding="utf-8")
            ids, invalid, source, warnings = _load_allowlist_from_file(path)
            self.assertEqual(ids, set())
            self.assertEqual(source, "missing")


# ---------------------------------------------------------------------------
# resolve_allowlist (env var)
# ---------------------------------------------------------------------------

class TestResolveAllowlist(unittest.TestCase):
    """Tests for resolve_allowlist() — env var / file / default precedence."""

    def test_env_var_takes_precedence(self):
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": "100,200,300"}, clear=False):
            ids, source, invalid, warnings = resolve_allowlist()
            self.assertEqual(source, "env")
            self.assertIn(100, ids)
            self.assertIn(200, ids)
            self.assertIn(300, ids)

    def test_env_var_invalid_entry(self):
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": "100,bad"}, clear=False):
            ids, source, invalid, warnings = resolve_allowlist()
            self.assertIn(100, ids)
            self.assertIn("bad", invalid)

    def test_empty_env_falls_through(self):
        env = {k: v for k, v in os.environ.items() if k != "ALLOWED_CHAT_IDS"}
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": ""}, clear=True):
            # Should not raise; falls through to file/default
            ids, source, invalid, warnings = resolve_allowlist()
            self.assertIsInstance(ids, set)

    def test_returns_tuple_of_four(self):
        with patch.dict(os.environ, {"ALLOWED_CHAT_IDS": "42"}, clear=False):
            result = resolve_allowlist()
            self.assertEqual(len(result), 4)


# ---------------------------------------------------------------------------
# is_chat_allowed (explicit allowlist)
# ---------------------------------------------------------------------------

class TestIsChatAllowed(unittest.TestCase):
    """Tests for is_chat_allowed() — hard gate with explicit allowlist."""

    def test_allowed_chat_returns_true(self):
        result = is_chat_allowed(111, allowlist={111, 222})
        self.assertTrue(result)

    def test_not_allowed_chat_returns_false(self):
        result = is_chat_allowed(999, allowlist={111, 222})
        self.assertFalse(result)

    def test_empty_allowlist_returns_false(self):
        result = is_chat_allowed(111, allowlist=set())
        self.assertFalse(result)

    def test_excluded_title_pattern_returns_false(self):
        # "responder" is in EXCLUDED_PATTERNS
        result = is_chat_allowed(111, chat_title="BotResponder", allowlist={111})
        self.assertFalse(result)

    def test_botfather_excluded(self):
        result = is_chat_allowed(111, chat_title="BotFather Official", allowlist={111})
        self.assertFalse(result)

    def test_raise_on_fail_raises_chat_not_allowed(self):
        with self.assertRaises(ChatNotAllowedError):
            is_chat_allowed(999, allowlist={111}, raise_on_fail=True)

    def test_chat_id_none_excluded_title_allowed(self):
        # Title None → no exclusion check on title
        result = is_chat_allowed(111, chat_title=None, allowlist={111})
        self.assertTrue(result)

    def test_returns_bool(self):
        self.assertIsInstance(is_chat_allowed(1, allowlist={1}), bool)


if __name__ == "__main__":
    unittest.main()
