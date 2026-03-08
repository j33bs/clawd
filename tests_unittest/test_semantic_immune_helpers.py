"""Tests for workspace/tacti/semantic_immune.py pure helpers.

Stubs tacti.config and tacti.events before import.

Covers:
- _vec
- _norm
- _cos
- _median
- _mad
- _normalize_claim
- _claim_signature
- _jaccard
- _paths
- _load_stats
- _save_stats
- _append
"""
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_tacti_stubs():
    """Install tacti.config and tacti.events stubs if not already present."""
    tacti_pkg = sys.modules.get("tacti")
    if tacti_pkg is None:
        tacti_pkg = types.ModuleType("tacti")
        tacti_pkg.__path__ = [str(REPO_ROOT / "workspace" / "tacti")]
        sys.modules["tacti"] = tacti_pkg

    if "tacti.config" not in sys.modules:
        config_mod = types.ModuleType("tacti.config")
        config_mod.get_int = lambda key, default, clamp=None: default
        config_mod.get_float = lambda key, default, clamp=None: default
        config_mod.is_enabled = lambda key: False
        sys.modules["tacti.config"] = config_mod

    if "tacti.events" not in sys.modules:
        events_mod = types.ModuleType("tacti.events")
        events_mod.emit = lambda *a, **kw: None
        sys.modules["tacti.events"] = events_mod


_ensure_tacti_stubs()

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti import semantic_immune as si  # noqa: E402


# ---------------------------------------------------------------------------
# _vec
# ---------------------------------------------------------------------------

class TestVec(unittest.TestCase):
    """Tests for _vec() — deterministic hash-projection embedding."""

    def test_returns_list_of_correct_dim(self):
        result = si._vec("hello world", dim=64)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 64)

    def test_custom_dim(self):
        result = si._vec("test", dim=128)
        self.assertEqual(len(result), 128)

    def test_empty_string_returns_zeros(self):
        result = si._vec("", dim=16)
        self.assertEqual(result, [0.0] * 16)

    def test_deterministic_same_text(self):
        a = si._vec("hello world")
        b = si._vec("hello world")
        self.assertEqual(a, b)

    def test_different_texts_differ(self):
        a = si._vec("apple")
        b = si._vec("banana")
        self.assertNotEqual(a, b)

    def test_single_token_nonzero(self):
        result = si._vec("uniquetoken", dim=64)
        self.assertTrue(any(x != 0.0 for x in result))


# ---------------------------------------------------------------------------
# _norm
# ---------------------------------------------------------------------------

class TestNorm(unittest.TestCase):
    """Tests for _norm() — L2 norm of a float vector."""

    def test_zero_vector_returns_zero(self):
        self.assertAlmostEqual(si._norm([0.0, 0.0, 0.0]), 0.0)

    def test_unit_vector(self):
        self.assertAlmostEqual(si._norm([1.0, 0.0, 0.0]), 1.0)

    def test_known_value(self):
        # norm([3, 4]) = 5
        self.assertAlmostEqual(si._norm([3.0, 4.0]), 5.0)

    def test_negative_elements(self):
        self.assertAlmostEqual(si._norm([-3.0, -4.0]), 5.0)

    def test_returns_float(self):
        result = si._norm([1.0, 2.0])
        self.assertIsInstance(result, float)


# ---------------------------------------------------------------------------
# _cos
# ---------------------------------------------------------------------------

class TestCos(unittest.TestCase):
    """Tests for _cos() — cosine similarity between two vectors."""

    def test_same_vector_is_one(self):
        v = [1.0, 2.0, 3.0]
        result = si._cos(v, v)
        self.assertAlmostEqual(result, 1.0)

    def test_zero_vector_returns_zero(self):
        self.assertAlmostEqual(si._cos([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_both_zero_returns_zero(self):
        self.assertAlmostEqual(si._cos([0.0], [0.0]), 0.0)

    def test_orthogonal_is_zero(self):
        self.assertAlmostEqual(si._cos([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_direction_is_minus_one(self):
        result = si._cos([1.0, 0.0], [-1.0, 0.0])
        self.assertAlmostEqual(result, -1.0)

    def test_bounded_result(self):
        a = si._vec("hello world")
        b = si._vec("foo bar baz")
        result = si._cos(a, b)
        self.assertGreaterEqual(result, -1.0)
        self.assertLessEqual(result, 1.0)


# ---------------------------------------------------------------------------
# _median
# ---------------------------------------------------------------------------

class TestMedian(unittest.TestCase):
    """Tests for _median() — median of a float list."""

    def test_empty_returns_zero(self):
        self.assertAlmostEqual(si._median([]), 0.0)

    def test_single_element(self):
        self.assertAlmostEqual(si._median([7.0]), 7.0)

    def test_odd_length(self):
        self.assertAlmostEqual(si._median([1.0, 3.0, 2.0]), 2.0)

    def test_even_length(self):
        self.assertAlmostEqual(si._median([1.0, 2.0, 3.0, 4.0]), 2.5)

    def test_already_sorted(self):
        self.assertAlmostEqual(si._median([10.0, 20.0, 30.0]), 20.0)


# ---------------------------------------------------------------------------
# _mad
# ---------------------------------------------------------------------------

class TestMad(unittest.TestCase):
    """Tests for _mad() — median absolute deviation."""

    def test_empty_returns_zero(self):
        self.assertAlmostEqual(si._mad([]), 0.0)

    def test_identical_values_returns_zero(self):
        self.assertAlmostEqual(si._mad([5.0, 5.0, 5.0]), 0.0)

    def test_known_values(self):
        # median([1,2,3,4,5]) = 3, deviations = [2,1,0,1,2], median=1
        self.assertAlmostEqual(si._mad([1.0, 2.0, 3.0, 4.0, 5.0]), 1.0)

    def test_single_element(self):
        self.assertAlmostEqual(si._mad([42.0]), 0.0)

    def test_returns_float(self):
        result = si._mad([1.0, 2.0, 3.0])
        self.assertIsInstance(result, float)


# ---------------------------------------------------------------------------
# _normalize_claim
# ---------------------------------------------------------------------------

class TestNormalizeClaim(unittest.TestCase):
    """Tests for _normalize_claim() — lowercase tokenize a claim string."""

    def test_empty_string_returns_empty(self):
        self.assertEqual(si._normalize_claim(""), [])

    def test_basic_tokenization(self):
        result = si._normalize_claim("Hello World")
        self.assertEqual(result, ["hello", "world"])

    def test_strips_punctuation(self):
        result = si._normalize_claim("hello, world!")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_numbers_included(self):
        result = si._normalize_claim("version 3 update")
        self.assertIn("3", result)

    def test_underscores_included(self):
        result = si._normalize_claim("feature_flag")
        self.assertIn("feature_flag", result)

    def test_returns_list(self):
        result = si._normalize_claim("test")
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# _claim_signature
# ---------------------------------------------------------------------------

class TestClaimSignature(unittest.TestCase):
    """Tests for _claim_signature() — builds token set + hash digest."""

    def test_has_tokens_key(self):
        result = si._claim_signature("hello world")
        self.assertIn("tokens", result)

    def test_has_digest_key(self):
        result = si._claim_signature("hello world")
        self.assertIn("digest", result)

    def test_digest_is_hex_string(self):
        digest = si._claim_signature("test")["digest"]
        int(digest, 16)  # should not raise

    def test_digest_length_16(self):
        digest = si._claim_signature("anything")["digest"]
        self.assertEqual(len(digest), 16)

    def test_tokens_are_sorted_unique(self):
        result = si._claim_signature("b a b c a")
        tokens = result["tokens"]
        self.assertEqual(tokens, sorted(set(tokens)))

    def test_empty_claim_empty_tokens(self):
        result = si._claim_signature("")
        self.assertEqual(result["tokens"], [])

    def test_deterministic(self):
        a = si._claim_signature("same text")
        b = si._claim_signature("same text")
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# _jaccard
# ---------------------------------------------------------------------------

class TestJaccard(unittest.TestCase):
    """Tests for _jaccard() — Jaccard similarity between two token lists."""

    def test_both_empty_returns_one(self):
        self.assertAlmostEqual(si._jaccard([], []), 1.0)

    def test_one_empty_returns_zero(self):
        self.assertAlmostEqual(si._jaccard(["a", "b"], []), 0.0)
        self.assertAlmostEqual(si._jaccard([], ["a", "b"]), 0.0)

    def test_identical_returns_one(self):
        self.assertAlmostEqual(si._jaccard(["a", "b"], ["a", "b"]), 1.0)

    def test_disjoint_returns_zero(self):
        self.assertAlmostEqual(si._jaccard(["a", "b"], ["c", "d"]), 0.0)

    def test_partial_overlap(self):
        # intersection {"b"}, union {"a","b","c"} → 1/3
        result = si._jaccard(["a", "b"], ["b", "c"])
        self.assertAlmostEqual(result, 1.0 / 3.0)

    def test_returns_float(self):
        result = si._jaccard(["x"], ["x"])
        self.assertIsInstance(result, float)

    def test_treats_as_sets(self):
        # duplicates collapse to sets
        self.assertAlmostEqual(si._jaccard(["a", "a", "b"], ["a", "b"]), 1.0)


# ---------------------------------------------------------------------------
# _paths
# ---------------------------------------------------------------------------

class TestPaths(unittest.TestCase):
    """Tests for _paths() — returns dict of named paths under repo_root."""

    def test_returns_dict(self):
        result = si._paths(REPO_ROOT)
        self.assertIsInstance(result, dict)

    def test_contains_stats_key(self):
        result = si._paths(REPO_ROOT)
        self.assertIn("stats", result)

    def test_contains_quarantine_key(self):
        result = si._paths(REPO_ROOT)
        self.assertIn("quarantine", result)

    def test_contains_approvals_key(self):
        result = si._paths(REPO_ROOT)
        self.assertIn("approvals", result)

    def test_values_are_paths(self):
        for v in si._paths(REPO_ROOT).values():
            self.assertIsInstance(v, Path)


# ---------------------------------------------------------------------------
# _load_stats
# ---------------------------------------------------------------------------

class TestLoadStats(unittest.TestCase):
    """Tests for _load_stats() — loads stats JSON or returns safe defaults."""

    def test_missing_path_returns_defaults(self):
        result = si._load_stats(Path("/nonexistent/stats.json"))
        self.assertIn("count", result)
        self.assertIn("centroid", result)

    def test_valid_json_returned(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stats.json"
            p.write_text(json.dumps({"count": 5, "centroid": [0.1]}), encoding="utf-8")
            result = si._load_stats(p)
            self.assertEqual(result["count"], 5)

    def test_invalid_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stats.json"
            p.write_text("NOT JSON", encoding="utf-8")
            result = si._load_stats(p)
            self.assertEqual(result["count"], 0)

    def test_non_dict_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stats.json"
            p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            result = si._load_stats(p)
            self.assertEqual(result["count"], 0)


# ---------------------------------------------------------------------------
# _save_stats
# ---------------------------------------------------------------------------

class TestSaveStats(unittest.TestCase):
    """Tests for _save_stats() — writes stats dict to JSON file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "stats.json"
            si._save_stats(p, {"count": 3})
            self.assertTrue(p.exists())

    def test_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stats.json"
            si._save_stats(p, {"count": 7, "centroid": [0.1, 0.2]})
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(data["count"], 7)

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b" / "c" / "stats.json"
            si._save_stats(p, {"count": 0})
            self.assertTrue(p.parent.is_dir())


# ---------------------------------------------------------------------------
# _append
# ---------------------------------------------------------------------------

class TestAppend(unittest.TestCase):
    """Tests for _append() — appends a JSONL row to a file."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "rows.jsonl"
            si._append(p, {"key": "value"})
            self.assertTrue(p.exists())

    def test_appends_valid_json_line(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rows.jsonl"
            si._append(p, {"x": 1})
            line = p.read_text(encoding="utf-8").strip()
            data = json.loads(line)
            self.assertEqual(data["x"], 1)

    def test_multiple_appends(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rows.jsonl"
            si._append(p, {"n": 1})
            si._append(p, {"n": 2})
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["n"], 2)


if __name__ == "__main__":
    unittest.main()
