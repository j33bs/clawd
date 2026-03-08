import unittest
from pathlib import Path
import os
import json
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))
if str(REPO_ROOT / "workspace" / "hivemind" / "hivemind") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "hivemind" / "hivemind"))

from narrative_distill import (  # noqa: E402
    _episode_id,
    _episode_text,
    _episode_timestamp,
    _extract_entities,
    _extract_topics,
    _jaccard_tokens,
    _norm_tokens,
    canonicalize,
    distill_episodes,
    write_semantic_entries,
)


class TestNarrativeDistill(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_distillation_is_stable_for_fixed_fixture(self):
        episodes = [
            {"id": "e1", "text": "Router selected local provider for coding task", "timestamp_utc": "2026-02-20T00:00:00Z"},
            {"id": "e2", "text": "Router selected local provider for coding tasks", "timestamp_utc": "2026-02-20T00:00:01Z"},
            {"id": "e3", "text": "Witness ledger committed routing decision hash", "timestamp_utc": "2026-02-20T00:00:02Z"},
        ]
        out = distill_episodes(episodes, max_items=10)
        self.assertGreaterEqual(len(out), 2)
        self.assertEqual(out[0]["support_count"], 2)
        self.assertEqual(out[0]["source_ids"], ["e1", "e2"])
        self.assertIn("router", out[0]["topics"])
        self.assertEqual(out[0]["timestamp_utc"], "2026-02-20T00:00:00Z")

    def test_max_items_is_respected(self):
        episodes = [{"id": f"e{i}", "text": f"Episode {i} distinct token {i}"} for i in range(80)]
        out = distill_episodes(episodes, max_items=5)
        self.assertEqual(len(out), 5)

    def test_semantic_store_write_is_idempotent_when_flag_on(self):
        os.environ["OPENCLAW_NARRATIVE_DISTILL"] = "1"
        entries = [
            {
                "fact": "Router selected local provider for coding task",
                "entities": [],
                "topics": ["router"],
                "support_count": 2,
                "source_ids": ["e1", "e2"],
                "timestamp_utc": "2026-02-20T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "workspace" / "hivemind" / "data").mkdir(parents=True, exist_ok=True)
            first = write_semantic_entries(entries, repo_root=root)
            second = write_semantic_entries(entries, repo_root=root)
            trails = root / "workspace" / "hivemind" / "data" / "trails.jsonl"
            rows = [json.loads(line) for line in trails.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(first["added"], 1)
        self.assertEqual(second["added"], 0)
        self.assertEqual(len(rows), 1)

    def test_flag_off_produces_no_write(self):
        os.environ["OPENCLAW_NARRATIVE_DISTILL"] = "0"
        entries = [
            {
                "fact": "Router selected local provider for coding task",
                "entities": [],
                "topics": ["router"],
                "support_count": 2,
                "source_ids": ["e1", "e2"],
                "timestamp_utc": "2026-02-20T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = write_semantic_entries(entries, repo_root=root)
            trails = root / "workspace" / "hivemind" / "data" / "trails.jsonl"
        self.assertEqual(result["backend"], "disabled")
        self.assertEqual(result["added"], 0)
        self.assertFalse(trails.exists())


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# canonicalize
# ---------------------------------------------------------------------------

class TestCanonicalize(unittest.TestCase):
    def test_returns_bytes(self):
        self.assertIsInstance(canonicalize({"a": 1}), bytes)

    def test_keys_sorted(self):
        result = canonicalize({"z": 1, "a": 2}).decode("utf-8")
        self.assertLess(result.index('"a"'), result.index('"z"'))

    def test_deterministic(self):
        obj = {"x": [1, 2], "y": "hello"}
        self.assertEqual(canonicalize(obj), canonicalize(obj))

    def test_compact_no_spaces(self):
        result = canonicalize({"a": 1}).decode("utf-8")
        self.assertNotIn(" ", result)


# ---------------------------------------------------------------------------
# _norm_tokens
# ---------------------------------------------------------------------------

class TestNormTokens(unittest.TestCase):
    def test_lowercases(self):
        result = _norm_tokens("Hello World")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_empty_returns_empty(self):
        self.assertEqual(_norm_tokens(""), [])

    def test_special_chars_excluded(self):
        result = _norm_tokens("a!b#c")
        self.assertIn("a", result)
        # '!' and '#' are not in [A-Za-z0-9_./@-]
        self.assertNotIn("!", result)

    def test_returns_list(self):
        self.assertIsInstance(_norm_tokens("word"), list)


# ---------------------------------------------------------------------------
# _jaccard_tokens
# ---------------------------------------------------------------------------

class TestJaccardTokens(unittest.TestCase):
    def test_identical_texts_returns_1(self):
        self.assertAlmostEqual(_jaccard_tokens("alpha beta", "alpha beta"), 1.0)

    def test_disjoint_returns_0(self):
        self.assertAlmostEqual(_jaccard_tokens("aaa bbb", "ccc ddd"), 0.0)

    def test_partial_overlap(self):
        val = _jaccard_tokens("alpha beta", "alpha gamma")
        self.assertGreater(val, 0.0)
        self.assertLess(val, 1.0)

    def test_both_empty_returns_1(self):
        self.assertAlmostEqual(_jaccard_tokens("", ""), 1.0)

    def test_one_empty_returns_0(self):
        self.assertAlmostEqual(_jaccard_tokens("alpha", ""), 0.0)


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------

class TestExtractEntities(unittest.TestCase):
    def test_extracts_capitalized_tokens(self):
        result = _extract_entities("Router selected Claude for coding")
        self.assertIn("Router", result)
        self.assertIn("Claude", result)

    def test_at_mentions(self):
        result = _extract_entities("Ping @jeebs about this")
        self.assertIn("@jeebs", result)

    def test_max_10_returned(self):
        text = " ".join(f"Token{i}" for i in range(30))
        result = _extract_entities(text)
        self.assertLessEqual(len(result), 10)

    def test_empty_returns_empty(self):
        self.assertEqual(_extract_entities("just lowercase"), [])

    def test_returns_list(self):
        self.assertIsInstance(_extract_entities("Hello"), list)


# ---------------------------------------------------------------------------
# _extract_topics
# ---------------------------------------------------------------------------

class TestExtractTopics(unittest.TestCase):
    def test_most_frequent_word_first(self):
        texts = ["router router router", "router coding", "coding"]
        result = _extract_topics(texts, top_n=3)
        self.assertEqual(result[0], "router")

    def test_top_n_respected(self):
        texts = ["alpha beta gamma delta epsilon"]
        result = _extract_topics(texts, top_n=2)
        self.assertLessEqual(len(result), 2)

    def test_stopwords_excluded(self):
        # Common stopwords should not appear in topics
        texts = ["the quick brown fox"]
        result = _extract_topics(texts, top_n=5)
        self.assertNotIn("the", result)

    def test_returns_list(self):
        self.assertIsInstance(_extract_topics(["hello world"]), list)


# ---------------------------------------------------------------------------
# _episode_text
# ---------------------------------------------------------------------------

class TestEpisodeText(unittest.TestCase):
    def test_text_key_preferred(self):
        ep = {"text": "hello", "content": "other"}
        self.assertEqual(_episode_text(ep), "hello")

    def test_content_key_fallback(self):
        ep = {"content": "world"}
        self.assertEqual(_episode_text(ep), "world")

    def test_message_key_fallback(self):
        ep = {"message": "from message"}
        self.assertEqual(_episode_text(ep), "from message")

    def test_empty_ep_returns_empty(self):
        self.assertEqual(_episode_text({}), "")

    def test_whitespace_stripped(self):
        ep = {"text": "  hello  "}
        self.assertEqual(_episode_text(ep), "hello")


# ---------------------------------------------------------------------------
# _episode_id
# ---------------------------------------------------------------------------

class TestEpisodeId(unittest.TestCase):
    def test_id_key_used(self):
        ep = {"id": "ep-001"}
        self.assertEqual(_episode_id(ep, "fallback"), "ep-001")

    def test_event_id_key_fallback(self):
        ep = {"event_id": "ev-1"}
        self.assertEqual(_episode_id(ep, "fallback"), "ev-1")

    def test_fallback_hash_used(self):
        ep = {}
        result = _episode_id(ep, "unique fallback text")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 16)

    def test_fallback_deterministic(self):
        ep = {}
        r1 = _episode_id(ep, "same text")
        r2 = _episode_id(ep, "same text")
        self.assertEqual(r1, r2)


# ---------------------------------------------------------------------------
# _episode_timestamp
# ---------------------------------------------------------------------------

class TestEpisodeTimestamp(unittest.TestCase):
    def test_timestamp_utc_key(self):
        ep = {"timestamp_utc": "2026-01-15T12:00:00Z"}
        result = _episode_timestamp(ep)
        self.assertTrue(result.endswith("Z"))

    def test_ts_key_fallback(self):
        ep = {"ts": "2026-01-15T12:00:00Z"}
        result = _episode_timestamp(ep)
        self.assertTrue(result.endswith("Z"))

    def test_empty_ep_returns_empty(self):
        self.assertEqual(_episode_timestamp({}), "")

    def test_invalid_timestamp_returns_empty(self):
        self.assertEqual(_episode_timestamp({"timestamp_utc": "not-a-date"}), "")

    def test_returns_string(self):
        ep = {"timestamp_utc": "2026-01-15T12:00:00Z"}
        self.assertIsInstance(_episode_timestamp(ep), str)
