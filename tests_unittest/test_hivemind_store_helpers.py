"""Tests for pure helpers in workspace/hivemind/hivemind/store.py.

Requires relative-import stubs for .models and .redaction.
All pure helpers are staticmethods or classmethods on HiveMindStore.

Covers:
- HiveMindStore.content_hash (staticmethod)
- HiveMindStore._tokenize (staticmethod)
- HiveMindStore._is_expired (staticmethod)
- HiveMindStore._can_view (staticmethod)
- HiveMindStore._score (classmethod)
- HiveMindStore._load_hashes (instance, tempfile)
- HiveMindStore._save_hashes (instance, tempfile)
- HiveMindStore._append_jsonl (instance, tempfile)
- HiveMindStore.all_units (instance, tempfile)
"""
import importlib.util as _ilu
import json
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
HM_DIR = REPO_ROOT / "workspace" / "hivemind" / "hivemind"

# ---------------------------------------------------------------------------
# Set up hivemind.hivemind package + relative-import stubs
# ---------------------------------------------------------------------------

def _ensure_hivemind_pkg():
    if "hivemind" not in sys.modules:
        pkg = types.ModuleType("hivemind")
        pkg.__path__ = [str(HM_DIR.parent)]
        pkg.__package__ = "hivemind"
        sys.modules["hivemind"] = pkg
    if "hivemind.hivemind" not in sys.modules:
        sub = types.ModuleType("hivemind.hivemind")
        sub.__path__ = [str(HM_DIR)]
        sub.__package__ = "hivemind.hivemind"
        sys.modules["hivemind.hivemind"] = sub
        setattr(sys.modules["hivemind"], "hivemind", sub)

def _ensure_models_stub():
    if "hivemind.hivemind.models" not in sys.modules:
        mod = types.ModuleType("hivemind.hivemind.models")

        @dataclass
        class KnowledgeUnit:
            kind: str
            source: str
            agent_scope: str
            ttl_days: Optional[int] = None
            metadata: Dict[str, Any] = field(default_factory=dict)

        mod.KnowledgeUnit = KnowledgeUnit
        sys.modules["hivemind.hivemind.models"] = mod
        setattr(sys.modules["hivemind.hivemind"], "models", mod)

def _ensure_redaction_stub():
    if "hivemind.hivemind.redaction" not in sys.modules:
        mod = types.ModuleType("hivemind.hivemind.redaction")
        mod.redact_for_embedding = lambda text: text
        sys.modules["hivemind.hivemind.redaction"] = mod
        setattr(sys.modules["hivemind.hivemind"], "redaction", mod)


_ensure_hivemind_pkg()
_ensure_models_stub()
_ensure_redaction_stub()

_spec = _ilu.spec_from_file_location(
    "hivemind.hivemind.store",
    str(HM_DIR / "store.py"),
)
hs = _ilu.module_from_spec(_spec)
hs.__package__ = "hivemind.hivemind"
sys.modules["hivemind.hivemind.store"] = hs
_spec.loader.exec_module(hs)

HiveMindStore = hs.HiveMindStore


# ---------------------------------------------------------------------------
# content_hash (staticmethod)
# ---------------------------------------------------------------------------

class TestContentHash(unittest.TestCase):
    """Tests for HiveMindStore.content_hash() — SHA-256 of normalized content."""

    def test_returns_string(self):
        self.assertIsInstance(HiveMindStore.content_hash("hello"), str)

    def test_hex_length_64(self):
        self.assertEqual(len(HiveMindStore.content_hash("test")), 64)

    def test_deterministic(self):
        self.assertEqual(
            HiveMindStore.content_hash("hello world"),
            HiveMindStore.content_hash("hello world"),
        )

    def test_different_content_differs(self):
        self.assertNotEqual(
            HiveMindStore.content_hash("foo"),
            HiveMindStore.content_hash("bar"),
        )

    def test_trailing_whitespace_normalized(self):
        # Trailing spaces on lines should not affect hash
        self.assertEqual(
            HiveMindStore.content_hash("hello   \nworld"),
            HiveMindStore.content_hash("hello\nworld"),
        )

    def test_empty_string(self):
        result = HiveMindStore.content_hash("")
        self.assertEqual(len(result), 64)


# ---------------------------------------------------------------------------
# _tokenize (staticmethod)
# ---------------------------------------------------------------------------

class TestTokenize(unittest.TestCase):
    """Tests for HiveMindStore._tokenize() — alphanumeric tokenizer."""

    def test_basic_words(self):
        result = HiveMindStore._tokenize("hello world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_lowercase(self):
        result = HiveMindStore._tokenize("Hello World")
        self.assertIn("hello", result)
        self.assertNotIn("Hello", result)

    def test_hyphens_included(self):
        result = HiveMindStore._tokenize("foo-bar")
        self.assertIn("foo-bar", result)

    def test_underscores_included(self):
        result = HiveMindStore._tokenize("foo_bar")
        self.assertIn("foo_bar", result)

    def test_punctuation_splits(self):
        result = HiveMindStore._tokenize("hello,world")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_empty_string_returns_empty(self):
        self.assertEqual(HiveMindStore._tokenize(""), [])

    def test_returns_list(self):
        self.assertIsInstance(HiveMindStore._tokenize("test"), list)


# ---------------------------------------------------------------------------
# _is_expired (staticmethod)
# ---------------------------------------------------------------------------

class TestIsExpired(unittest.TestCase):
    """Tests for HiveMindStore._is_expired() — checks expiry timestamp."""

    def test_no_expires_at_returns_false(self):
        self.assertFalse(HiveMindStore._is_expired({}))

    def test_future_expiry_returns_false(self):
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        self.assertFalse(HiveMindStore._is_expired({"expires_at": future}))

    def test_past_expiry_returns_true(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.assertTrue(HiveMindStore._is_expired({"expires_at": past}))

    def test_invalid_expiry_returns_false(self):
        self.assertFalse(HiveMindStore._is_expired({"expires_at": "not-a-date"}))

    def test_returns_bool(self):
        result = HiveMindStore._is_expired({})
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# _can_view (staticmethod)
# ---------------------------------------------------------------------------

class TestCanView(unittest.TestCase):
    """Tests for HiveMindStore._can_view() — scope-based access control."""

    def test_shared_scope_always_viewable(self):
        self.assertTrue(HiveMindStore._can_view("agent_a", "shared"))

    def test_same_scope_viewable(self):
        self.assertTrue(HiveMindStore._can_view("agent_a", "agent_a"))

    def test_different_scope_not_viewable(self):
        self.assertFalse(HiveMindStore._can_view("agent_a", "agent_b"))

    def test_returns_bool(self):
        result = HiveMindStore._can_view("x", "y")
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# _score (classmethod)
# ---------------------------------------------------------------------------

class TestScore(unittest.TestCase):
    """Tests for HiveMindStore._score() — keyword match score."""

    def test_exact_match_scores_positive(self):
        result = HiveMindStore._score("active inference", "active inference theory")
        self.assertGreater(result, 0)

    def test_no_match_scores_zero(self):
        result = HiveMindStore._score("xyz", "abc def")
        self.assertEqual(result, 0)

    def test_full_phrase_in_content_gets_bonus(self):
        # When the full query appears in content, +3 bonus
        low = HiveMindStore._score("active", "active inference content")
        high = HiveMindStore._score("active inference", "active inference content")
        self.assertGreater(high, low)

    def test_empty_query_scores_zero(self):
        self.assertEqual(HiveMindStore._score("", "any content"), 0)

    def test_returns_int(self):
        self.assertIsInstance(HiveMindStore._score("a", "b"), int)


# ---------------------------------------------------------------------------
# _load_hashes / _save_hashes / _append_jsonl (instance methods)
# ---------------------------------------------------------------------------

class TestHiveMindStoreFileOps(unittest.TestCase):
    """Tests for instance file-I/O helpers using tempfile."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._store = HiveMindStore(base_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_hashes_missing_returns_empty_set(self):
        result = self._store._load_hashes()
        self.assertEqual(result, set())

    def test_save_then_load_hashes(self):
        hashes = {"abc123", "def456"}
        self._store._save_hashes(hashes)
        loaded = self._store._load_hashes()
        self.assertEqual(loaded, hashes)

    def test_load_hashes_invalid_json_returns_empty(self):
        self._store.hash_index_path.write_text("not json", encoding="utf-8")
        self.assertEqual(self._store._load_hashes(), set())

    def test_load_hashes_non_list_returns_empty(self):
        self._store.hash_index_path.write_text('{"a": 1}', encoding="utf-8")
        self.assertEqual(self._store._load_hashes(), set())

    def test_append_jsonl_creates_file(self):
        path = Path(self._tmp.name) / "test.jsonl"
        self._store._append_jsonl(path, {"key": "value"})
        self.assertTrue(path.exists())

    def test_append_jsonl_writes_valid_json(self):
        path = Path(self._tmp.name) / "test.jsonl"
        self._store._append_jsonl(path, {"x": 1})
        line = path.read_text(encoding="utf-8").strip()
        obj = json.loads(line)
        self.assertEqual(obj["x"], 1)

    def test_append_jsonl_multiple_rows(self):
        path = Path(self._tmp.name) / "test.jsonl"
        self._store._append_jsonl(path, {"n": 1})
        self._store._append_jsonl(path, {"n": 2})
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)


# ---------------------------------------------------------------------------
# all_units
# ---------------------------------------------------------------------------

class TestAllUnits(unittest.TestCase):
    """Tests for HiveMindStore.all_units() — reads JSONL units file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._store = HiveMindStore(base_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty(self):
        self.assertEqual(self._store.all_units(), [])

    def test_reads_valid_units(self):
        self._store.units_path.write_text(
            json.dumps({"kind": "note", "content": "test"}) + "\n",
            encoding="utf-8",
        )
        result = self._store.all_units()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "note")

    def test_blank_lines_skipped(self):
        self._store.units_path.write_text(
            json.dumps({"kind": "a"}) + "\n\n" + json.dumps({"kind": "b"}) + "\n",
            encoding="utf-8",
        )
        result = self._store.all_units()
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
