"""Tests for pure helpers in workspace/memory/message_hooks.py.

Stubs memory.arousal_tracker and memory.relationship_tracker.
Tests only the pure stdlib helpers.

Covers:
- _utc_now
- _normalize_text
- content_hash
- build_message_event
"""
import importlib.util as _ilu
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = REPO_ROOT / "workspace" / "memory"


def _ensure_memory_pkg():
    if "memory" not in sys.modules:
        pkg = types.ModuleType("memory")
        pkg.__path__ = [str(MEMORY_DIR)]
        pkg.__package__ = "memory"
        sys.modules["memory"] = pkg

    if "memory.arousal_tracker" not in sys.modules:
        at = types.ModuleType("memory.arousal_tracker")
        at.update_from_event = lambda *a, **kw: {"ok": True}
        sys.modules["memory.arousal_tracker"] = at
        setattr(sys.modules["memory"], "arousal_tracker", at)
    else:
        at = sys.modules["memory.arousal_tracker"]
        if not hasattr(at, "update_from_event"):
            at.update_from_event = lambda *a, **kw: {"ok": True}

    if "memory.relationship_tracker" not in sys.modules:
        rt = types.ModuleType("memory.relationship_tracker")
        rt.update_from_event = lambda *a, **kw: {"ok": True}
        sys.modules["memory.relationship_tracker"] = rt
        setattr(sys.modules["memory"], "relationship_tracker", rt)
    else:
        rt = sys.modules["memory.relationship_tracker"]
        if not hasattr(rt, "update_from_event"):
            rt.update_from_event = lambda *a, **kw: {"ok": True}


_ensure_memory_pkg()

_spec = _ilu.spec_from_file_location(
    "memory_message_hooks_real",
    str(MEMORY_DIR / "message_hooks.py"),
)
mh = _ilu.module_from_spec(_spec)
mh.__package__ = "memory"
sys.modules["memory_message_hooks_real"] = mh
_spec.loader.exec_module(mh)


# ---------------------------------------------------------------------------
# _utc_now
# ---------------------------------------------------------------------------

class TestUtcNow(unittest.TestCase):
    """Tests for _utc_now() — UTC ISO string with Z suffix, no microseconds."""

    def test_returns_string(self):
        self.assertIsInstance(mh._utc_now(), str)

    def test_ends_with_z(self):
        self.assertTrue(mh._utc_now().endswith("Z"))

    def test_no_microseconds(self):
        result = mh._utc_now()
        self.assertNotIn(".", result)

    def test_parseable(self):
        result = mh._utc_now()
        datetime.fromisoformat(result.replace("Z", "+00:00"))

    def test_contains_t_separator(self):
        result = mh._utc_now()
        self.assertIn("T", result)


# ---------------------------------------------------------------------------
# _normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText(unittest.TestCase):
    """Tests for _normalize_text() — collapses whitespace."""

    def test_collapses_internal_spaces(self):
        result = mh._normalize_text("hello   world")
        self.assertEqual(result, "hello world")

    def test_strips_leading_trailing(self):
        result = mh._normalize_text("  hello  ")
        self.assertEqual(result, "hello")

    def test_collapses_tabs_and_newlines(self):
        result = mh._normalize_text("hello\t\nworld")
        self.assertEqual(result, "hello world")

    def test_empty_string(self):
        result = mh._normalize_text("")
        self.assertEqual(result, "")

    def test_none_becomes_empty(self):
        result = mh._normalize_text(None)
        self.assertEqual(result, "")

    def test_single_word_unchanged(self):
        result = mh._normalize_text("hello")
        self.assertEqual(result, "hello")


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------

class TestContentHash(unittest.TestCase):
    """Tests for content_hash() — sha256 hex of normalized text."""

    def test_returns_string(self):
        result = mh.content_hash("hello")
        self.assertIsInstance(result, str)

    def test_returns_64_char_hex(self):
        result = mh.content_hash("hello")
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_deterministic(self):
        a = mh.content_hash("same text")
        b = mh.content_hash("same text")
        self.assertEqual(a, b)

    def test_normalizes_before_hashing(self):
        # "hello  world" and "hello world" should hash the same
        a = mh.content_hash("hello  world")
        b = mh.content_hash("hello world")
        self.assertEqual(a, b)

    def test_different_text_different_hash(self):
        a = mh.content_hash("text one")
        b = mh.content_hash("text two")
        self.assertNotEqual(a, b)

    def test_empty_string(self):
        result = mh.content_hash("")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)


# ---------------------------------------------------------------------------
# build_message_event
# ---------------------------------------------------------------------------

class TestBuildMessageEvent(unittest.TestCase):
    """Tests for build_message_event() — builds a message event dict."""

    def _make(self, **kw):
        defaults = dict(session_id="sess-1", role="user", content="hello")
        defaults.update(kw)
        return mh.build_message_event(**defaults)

    def test_returns_dict(self):
        result = self._make()
        self.assertIsInstance(result, dict)

    def test_session_id_stored(self):
        result = self._make(session_id="my-session")
        self.assertEqual(result["session_id"], "my-session")

    def test_role_stored(self):
        result = self._make(role="assistant")
        self.assertEqual(result["role"], "assistant")

    def test_content_hash_present(self):
        result = self._make(content="some content")
        self.assertIn("content_hash", result)
        self.assertIsInstance(result["content_hash"], str)

    def test_content_hash_matches(self):
        result = self._make(content="hello world")
        expected = mh.content_hash("hello world")
        self.assertEqual(result["content_hash"], expected)

    def test_default_source_teamchat(self):
        result = self._make()
        self.assertEqual(result["source"], "teamchat")

    def test_custom_source(self):
        result = self._make(source="telegram")
        self.assertEqual(result["source"], "telegram")

    def test_ts_utc_provided(self):
        result = self._make(ts_utc="2026-01-01T12:00:00Z")
        self.assertEqual(result["ts_utc"], "2026-01-01T12:00:00Z")

    def test_ts_utc_auto_generated(self):
        result = self._make(ts_utc=None)
        self.assertIn("ts_utc", result)
        self.assertIsInstance(result["ts_utc"], str)

    def test_type_is_message_event(self):
        result = self._make()
        self.assertEqual(result["type"], "message_event")

    def test_tone_default_unlabeled(self):
        result = self._make()
        self.assertEqual(result["tone"], "unlabeled")


if __name__ == "__main__":
    unittest.main()
