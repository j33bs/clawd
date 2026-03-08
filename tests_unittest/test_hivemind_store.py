"""Tests for hivemind.store — HiveMindStore pure static methods + I/O helpers."""
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_DIR = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_DIR) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_DIR))

from hivemind.store import HiveMindStore


def _store(tmp_path: Path) -> HiveMindStore:
    return HiveMindStore(tmp_path)


class TestContentHash(unittest.TestCase):
    """Tests for HiveMindStore.content_hash() — deterministic SHA256."""

    def test_returns_string(self):
        result = HiveMindStore.content_hash("hello")
        self.assertIsInstance(result, str)

    def test_is_hex_sha256_length(self):
        result = HiveMindStore.content_hash("hello")
        self.assertEqual(len(result), 64)

    def test_deterministic(self):
        self.assertEqual(
            HiveMindStore.content_hash("hello"),
            HiveMindStore.content_hash("hello"),
        )

    def test_different_content_different_hash(self):
        self.assertNotEqual(
            HiveMindStore.content_hash("hello"),
            HiveMindStore.content_hash("world"),
        )

    def test_trailing_whitespace_normalized(self):
        # Lines are rstrip()d before hashing
        self.assertEqual(
            HiveMindStore.content_hash("hello   "),
            HiveMindStore.content_hash("hello"),
        )

    def test_leading_trailing_blank_lines_normalized(self):
        self.assertEqual(
            HiveMindStore.content_hash("\nhello\n\n"),
            HiveMindStore.content_hash("hello"),
        )

    def test_empty_string(self):
        result = HiveMindStore.content_hash("")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)

    def test_none_equivalent_to_empty(self):
        # None is coerced via `content or ""`
        result_empty = HiveMindStore.content_hash("")
        result_none = HiveMindStore.content_hash(None)  # type: ignore[arg-type]
        self.assertEqual(result_empty, result_none)


class TestTokenize(unittest.TestCase):
    """Tests for HiveMindStore._tokenize() — word-boundary tokenizer."""

    def test_empty_returns_empty(self):
        self.assertEqual(HiveMindStore._tokenize(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(HiveMindStore._tokenize(None), [])  # type: ignore[arg-type]

    def test_simple_word(self):
        self.assertIn("hello", HiveMindStore._tokenize("hello"))

    def test_lowercase(self):
        tokens = HiveMindStore._tokenize("Hello World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_hyphen_kept_in_token(self):
        tokens = HiveMindStore._tokenize("hello-world")
        self.assertIn("hello-world", tokens)

    def test_underscore_kept_in_token(self):
        tokens = HiveMindStore._tokenize("foo_bar")
        self.assertIn("foo_bar", tokens)

    def test_numbers_kept(self):
        tokens = HiveMindStore._tokenize("model123")
        self.assertIn("model123", tokens)

    def test_punctuation_splits(self):
        tokens = HiveMindStore._tokenize("hello,world")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_returns_list(self):
        self.assertIsInstance(HiveMindStore._tokenize("hello"), list)

    def test_multiple_words(self):
        tokens = HiveMindStore._tokenize("a b c d")
        self.assertEqual(sorted(tokens), ["a", "b", "c", "d"])


class TestIsExpired(unittest.TestCase):
    """Tests for HiveMindStore._is_expired() — TTL check."""

    def test_empty_unit_not_expired(self):
        self.assertFalse(HiveMindStore._is_expired({}))

    def test_no_expires_at_not_expired(self):
        self.assertFalse(HiveMindStore._is_expired({"content": "hello"}))

    def test_none_expires_at_not_expired(self):
        self.assertFalse(HiveMindStore._is_expired({"expires_at": None}))

    def test_future_expires_at_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self.assertFalse(HiveMindStore._is_expired({"expires_at": future}))

    def test_past_expires_at_is_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.assertTrue(HiveMindStore._is_expired({"expires_at": past}))

    def test_invalid_expires_at_not_expired(self):
        self.assertFalse(HiveMindStore._is_expired({"expires_at": "not-a-date"}))

    def test_returns_bool(self):
        result = HiveMindStore._is_expired({})
        self.assertIsInstance(result, bool)


class TestCanView(unittest.TestCase):
    """Tests for HiveMindStore._can_view() — agent scope access control."""

    def test_shared_scope_always_viewable(self):
        self.assertTrue(HiveMindStore._can_view("agent_a", "shared"))

    def test_own_scope_viewable(self):
        self.assertTrue(HiveMindStore._can_view("agent_a", "agent_a"))

    def test_other_agent_scope_not_viewable(self):
        self.assertFalse(HiveMindStore._can_view("agent_a", "agent_b"))

    def test_empty_agent_scope_not_shared(self):
        self.assertFalse(HiveMindStore._can_view("agent_a", ""))

    def test_returns_bool(self):
        result = HiveMindStore._can_view("a", "shared")
        self.assertIsInstance(result, bool)


class TestScore(unittest.TestCase):
    """Tests for HiveMindStore._score() — token-overlap relevance scoring."""

    def test_empty_query_returns_zero(self):
        self.assertEqual(HiveMindStore._score("", "any content here"), 0)

    def test_no_overlap_returns_zero(self):
        self.assertEqual(HiveMindStore._score("apples", "oranges bananas"), 0)

    def test_single_overlap_returns_one(self):
        score = HiveMindStore._score("consciousness", "consciousness routing")
        self.assertGreaterEqual(score, 1)

    def test_exact_substring_bonus(self):
        # Exact query as substring gets +3 bonus
        score_exact = HiveMindStore._score("hello world", "hello world here")
        score_partial = HiveMindStore._score("hello world", "hello xyzzy world abc")
        self.assertGreater(score_exact, score_partial)

    def test_more_overlap_higher_score(self):
        s1 = HiveMindStore._score("a b c", "a b c d e")
        s2 = HiveMindStore._score("a b c", "a x y z w")
        self.assertGreater(s1, s2)

    def test_returns_int(self):
        result = HiveMindStore._score("hello", "hello world")
        self.assertIsInstance(result, int)


class TestAllUnitsWriteUnits(unittest.TestCase):
    """Tests for HiveMindStore.all_units() and write_units() — JSONL I/O."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = _store(Path(self._tmpdir.name))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_all_units_empty_returns_empty(self):
        self.assertEqual(self.store.all_units(), [])

    def test_write_then_read_roundtrip(self):
        units = [{"kind": "observation", "content": "hello"}]
        self.store.write_units(units)
        result = self.store.all_units()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "observation")

    def test_write_multiple_units(self):
        units = [{"id": i} for i in range(5)]
        self.store.write_units(units)
        self.assertEqual(len(self.store.all_units()), 5)

    def test_write_overwrites_previous(self):
        self.store.write_units([{"id": 1}])
        self.store.write_units([{"id": 2}, {"id": 3}])
        result = self.store.all_units()
        self.assertEqual(len(result), 2)

    def test_all_units_skips_invalid_json_lines(self):
        # Write a valid unit then corrupt the file slightly
        self.store.write_units([{"kind": "obs"}])
        with self.store.units_path.open("a", encoding="utf-8") as fh:
            fh.write("not valid json\n")
        result = self.store.all_units()
        self.assertEqual(len(result), 1)

    def test_all_units_returns_list_of_dicts(self):
        self.store.write_units([{"x": 1}])
        result = self.store.all_units()
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)


class TestHashIndex(unittest.TestCase):
    """Tests for _load_hashes() and _save_hashes() — dedup index."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = _store(Path(self._tmpdir.name))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_load_hashes_missing_returns_empty(self):
        result = self.store._load_hashes()
        self.assertEqual(result, set())

    def test_save_then_load_roundtrip(self):
        hashes = {"abc123", "def456"}
        self.store._save_hashes(hashes)
        loaded = self.store._load_hashes()
        self.assertEqual(loaded, hashes)

    def test_save_deduplicates(self):
        self.store._save_hashes(["aaa", "aaa", "bbb"])
        loaded = self.store._load_hashes()
        self.assertEqual(len(loaded), 2)

    def test_load_returns_set(self):
        self.store._save_hashes(["x"])
        result = self.store._load_hashes()
        self.assertIsInstance(result, set)

    def test_invalid_hash_index_returns_empty(self):
        self.store.hash_index_path.write_text("not valid json", encoding="utf-8")
        result = self.store._load_hashes()
        self.assertEqual(result, set())


class TestReadLog(unittest.TestCase):
    """Tests for log_event() and read_log() — event log I/O."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = _store(Path(self._tmpdir.name))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_read_log_missing_returns_empty(self):
        self.assertEqual(self.store.read_log(), [])

    def test_log_event_then_read(self):
        self.store.log_event("test_event", key="val")
        log = self.store.read_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event"], "test_event")
        self.assertEqual(log[0]["key"], "val")

    def test_log_event_includes_ts_utc(self):
        self.store.log_event("ts_test")
        log = self.store.read_log()
        self.assertIn("ts_utc", log[0])

    def test_log_multiple_events_appends(self):
        self.store.log_event("first")
        self.store.log_event("second")
        log = self.store.read_log()
        self.assertEqual(len(log), 2)
        events = [e["event"] for e in log]
        self.assertIn("first", events)
        self.assertIn("second", events)


if __name__ == "__main__":
    unittest.main()
