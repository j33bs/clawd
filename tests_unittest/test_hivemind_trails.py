import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.trails import (  # noqa: E402
    TrailStore, _dot, _norm, _cosine, dampen_valence_signature, _parse_ts,
)


class TestTrailStore(unittest.TestCase):
    def test_decay_reduces_effective_strength(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trails.jsonl"
            store = TrailStore(path=path, half_life_hours=1.0)
            trail_id = store.add({"text": "route cache miss", "tags": ["routing"], "strength": 2.0, "meta": {}})
            now = datetime.now(timezone.utc)
            initial = store.query("route cache", k=1, now=now)[0]
            store.decay(now=now + timedelta(hours=2))
            later = store.query("route cache", k=1, now=now + timedelta(hours=2))[0]
            self.assertEqual(initial["trail_id"], trail_id)
            self.assertLess(later["effective_strength"], initial["effective_strength"])

    def test_reinforcement_increases_rank(self):
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl", half_life_hours=12.0)
            t1 = store.add({"text": "python memory tool", "tags": ["memory"], "strength": 1.0, "meta": {}})
            t2 = store.add({"text": "python memory tool stable", "tags": ["memory"], "strength": 1.0, "meta": {}})
            before = [x["trail_id"] for x in store.query("python memory", k=2)]
            store.reinforce(t2, 1.5)
            after = [x["trail_id"] for x in store.query("python memory", k=2)]
            self.assertIn(t1, before)
            self.assertEqual(after[0], t2)


class TestDot(unittest.TestCase):
    """Tests for trails._dot() — vector dot product."""

    def test_zero_vectors(self):
        self.assertAlmostEqual(_dot([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_identity_like(self):
        self.assertAlmostEqual(_dot([1.0, 0.0], [1.0, 0.0]), 1.0)

    def test_basic_product(self):
        self.assertAlmostEqual(_dot([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]), 32.0)

    def test_returns_float(self):
        self.assertIsInstance(_dot([1.0], [2.0]), float)

    def test_empty_vectors(self):
        self.assertAlmostEqual(_dot([], []), 0.0)

    def test_commutative(self):
        a, b = [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]
        self.assertAlmostEqual(_dot(a, b), _dot(b, a))


class TestNorm(unittest.TestCase):
    """Tests for trails._norm() — L2 norm."""

    def test_zero_vector_is_zero(self):
        self.assertAlmostEqual(_norm([0.0, 0.0, 0.0]), 0.0)

    def test_unit_vector(self):
        self.assertAlmostEqual(_norm([1.0, 0.0, 0.0]), 1.0)

    def test_3_4_5_triple(self):
        self.assertAlmostEqual(_norm([3.0, 4.0]), 5.0)

    def test_negative_values(self):
        self.assertAlmostEqual(_norm([-3.0, -4.0]), 5.0)

    def test_returns_float(self):
        self.assertIsInstance(_norm([1.0, 2.0]), float)


class TestCosine(unittest.TestCase):
    """Tests for trails._cosine() — cosine similarity."""

    def test_identical_vectors_return_one(self):
        v = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(_cosine(v, v), 1.0, places=5)

    def test_orthogonal_vectors_return_zero(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [0.0, 1.0]), 0.0, places=10)

    def test_zero_vector_returns_zero(self):
        self.assertAlmostEqual(_cosine([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_antiparallel_returns_minus_one(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [-1.0, 0.0]), -1.0, places=5)

    def test_symmetric(self):
        a, b = [1.0, 2.0], [3.0, 4.0]
        self.assertAlmostEqual(_cosine(a, b), _cosine(b, a), places=10)

    def test_returns_float(self):
        self.assertIsInstance(_cosine([1.0], [1.0]), float)


class TestDampenValenceSignature(unittest.TestCase):
    """Tests for trails.dampen_valence_signature()."""

    def test_float_halved_at_hop_1(self):
        self.assertAlmostEqual(dampen_valence_signature(1.0, hops=1), 0.5, places=5)

    def test_float_quartered_at_hop_2(self):
        self.assertAlmostEqual(dampen_valence_signature(1.0, hops=2), 0.25, places=5)

    def test_hop_0_unchanged(self):
        self.assertAlmostEqual(dampen_valence_signature(1.0, hops=0), 1.0, places=5)

    def test_dict_values_dampened(self):
        sig = {"a": 1.0, "b": 2.0}
        result = dampen_valence_signature(sig, hops=1)
        self.assertAlmostEqual(result["a"], 0.5, places=5)
        self.assertAlmostEqual(result["b"], 1.0, places=5)

    def test_list_values_dampened(self):
        result = dampen_valence_signature([1.0, 2.0], hops=1)
        self.assertAlmostEqual(result[0], 0.5, places=5)
        self.assertAlmostEqual(result[1], 1.0, places=5)

    def test_non_numeric_returns_none(self):
        self.assertIsNone(dampen_valence_signature("string", hops=1))

    def test_dict_non_numeric_values_excluded(self):
        sig = {"a": 1.0, "b": "text"}
        result = dampen_valence_signature(sig, hops=1)
        self.assertNotIn("b", result)

    def test_int_dampened(self):
        result = dampen_valence_signature(4, hops=2)
        self.assertAlmostEqual(result, 1.0, places=5)


class TestParseTs(unittest.TestCase):
    """Tests for trails._parse_ts() — flexible timestamp parser."""

    def test_z_suffix_parsed(self):
        result = _parse_ts("2026-03-08T12:00:00Z")
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.year, 2026)

    def test_datetime_passthrough(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = _parse_ts(dt)
        self.assertEqual(result, dt)

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2026, 1, 1)
        result = _parse_ts(dt)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_invalid_string_returns_now(self):
        before = datetime.now(timezone.utc)
        result = _parse_ts("not-a-date")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_returns_datetime(self):
        self.assertIsInstance(_parse_ts("2026-01-01T00:00:00Z"), datetime)


if __name__ == "__main__":
    unittest.main()

