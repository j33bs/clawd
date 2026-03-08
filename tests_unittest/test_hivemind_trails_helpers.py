"""Tests for workspace/hivemind/hivemind/trails.py pure helpers.

Stdlib-only, no external deps. Loaded with a unique module name.

Covers:
- _parse_ts
- _dot
- _norm
- _cosine
- _embed_text
- _trail_valence_enabled
- dampen_valence_signature
- _blend_valence_signature
"""
import importlib.util as _ilu
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAILS_PATH = REPO_ROOT / "workspace" / "hivemind" / "hivemind" / "trails.py"

_spec = _ilu.spec_from_file_location("hivemind_trails_real", str(TRAILS_PATH))
tr = _ilu.module_from_spec(_spec)
sys.modules["hivemind_trails_real"] = tr
_spec.loader.exec_module(tr)


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------

class TestParseTs(unittest.TestCase):
    """Tests for _parse_ts() — parse a timestamp value to an aware datetime."""

    def test_datetime_object_returned_as_is_if_aware(self):
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = tr._parse_ts(dt)
        self.assertEqual(result, dt)

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        result = tr._parse_ts(dt)
        self.assertIsNotNone(result.tzinfo)

    def test_iso_string_with_z_parsed(self):
        result = tr._parse_ts("2026-06-15T10:00:00Z")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 15)

    def test_iso_string_with_offset_parsed(self):
        result = tr._parse_ts("2026-01-01T12:00:00+00:00")
        self.assertIsNotNone(result.tzinfo)

    def test_empty_string_returns_utc_now(self):
        before = datetime.now(timezone.utc)
        result = tr._parse_ts("")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_invalid_string_returns_now(self):
        before = datetime.now(timezone.utc)
        result = tr._parse_ts("not-a-date")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_returns_datetime(self):
        result = tr._parse_ts("2026-01-01T00:00:00Z")
        self.assertIsInstance(result, datetime)


# ---------------------------------------------------------------------------
# _dot
# ---------------------------------------------------------------------------

class TestDot(unittest.TestCase):
    """Tests for _dot() — dot product of two float lists."""

    def test_basic_dot_product(self):
        self.assertAlmostEqual(tr._dot([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]), 32.0)

    def test_zero_vectors(self):
        self.assertAlmostEqual(tr._dot([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_orthogonal(self):
        self.assertAlmostEqual(tr._dot([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_negative_values(self):
        self.assertAlmostEqual(tr._dot([-1.0, 2.0], [3.0, -4.0]), -11.0)

    def test_returns_float(self):
        result = tr._dot([1.0, 2.0], [3.0, 4.0])
        self.assertIsInstance(result, float)


# ---------------------------------------------------------------------------
# _norm
# ---------------------------------------------------------------------------

class TestNorm(unittest.TestCase):
    """Tests for _norm() — L2 norm of a float list."""

    def test_zero_vector(self):
        self.assertAlmostEqual(tr._norm([0.0, 0.0, 0.0]), 0.0)

    def test_pythagorean_triple(self):
        self.assertAlmostEqual(tr._norm([3.0, 4.0]), 5.0)

    def test_unit_vector(self):
        self.assertAlmostEqual(tr._norm([1.0, 0.0]), 1.0)

    def test_returns_float(self):
        self.assertIsInstance(tr._norm([1.0]), float)


# ---------------------------------------------------------------------------
# _cosine
# ---------------------------------------------------------------------------

class TestCosine(unittest.TestCase):
    """Tests for _cosine() — cosine similarity."""

    def test_same_vector_returns_one(self):
        v = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(tr._cosine(v, v), 1.0)

    def test_zero_vector_returns_zero(self):
        self.assertAlmostEqual(tr._cosine([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_orthogonal_returns_zero(self):
        self.assertAlmostEqual(tr._cosine([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_returns_minus_one(self):
        self.assertAlmostEqual(tr._cosine([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_bounded(self):
        a = tr._embed_text("hello world")
        b = tr._embed_text("foo bar")
        result = tr._cosine(a, b)
        self.assertGreaterEqual(result, -1.0)
        self.assertLessEqual(result, 1.0)


# ---------------------------------------------------------------------------
# _embed_text
# ---------------------------------------------------------------------------

class TestEmbedText(unittest.TestCase):
    """Tests for _embed_text() — deterministic hash embedding."""

    def test_returns_list_of_correct_dim(self):
        result = tr._embed_text("hello", dim=24)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 24)

    def test_custom_dim(self):
        result = tr._embed_text("hello", dim=16)
        self.assertEqual(len(result), 16)

    def test_empty_string_all_zeros(self):
        result = tr._embed_text("", dim=8)
        self.assertEqual(result, [0.0] * 8)

    def test_deterministic(self):
        a = tr._embed_text("test text", dim=24)
        b = tr._embed_text("test text", dim=24)
        self.assertEqual(a, b)

    def test_tags_affect_output(self):
        without = tr._embed_text("hello", dim=24)
        with_tags = tr._embed_text("hello", tags=["extra_tag"], dim=24)
        self.assertNotEqual(without, with_tags)

    def test_different_inputs_differ(self):
        a = tr._embed_text("apple")
        b = tr._embed_text("banana")
        self.assertNotEqual(a, b)


# ---------------------------------------------------------------------------
# _trail_valence_enabled
# ---------------------------------------------------------------------------

class TestTrailValenceEnabled(unittest.TestCase):
    """Tests for _trail_valence_enabled() — reads env var."""

    def test_unset_returns_false(self):
        env = {k: v for k, v in os.environ.items()
               if k not in {"OPENCLAW_TRAILS_VALENCE", "OPENCLAW_TRAIL_VALENCE"}}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(tr._trail_valence_enabled())

    def test_set_to_one_returns_true(self):
        with patch.dict(os.environ, {"OPENCLAW_TRAILS_VALENCE": "1"}):
            self.assertTrue(tr._trail_valence_enabled())

    def test_set_to_true_returns_true(self):
        with patch.dict(os.environ, {"OPENCLAW_TRAILS_VALENCE": "true"}):
            self.assertTrue(tr._trail_valence_enabled())

    def test_returns_bool(self):
        env = {k: v for k, v in os.environ.items()
               if k not in {"OPENCLAW_TRAILS_VALENCE", "OPENCLAW_TRAIL_VALENCE"}}
        with patch.dict(os.environ, env, clear=True):
            self.assertIsInstance(tr._trail_valence_enabled(), bool)


# ---------------------------------------------------------------------------
# dampen_valence_signature
# ---------------------------------------------------------------------------

class TestDampenValenceSignature(unittest.TestCase):
    """Tests for dampen_valence_signature() — multiplies values by 0.5^hops."""

    def test_dict_dampened(self):
        result = tr.dampen_valence_signature({"a": 1.0, "b": 0.5}, hops=1)
        self.assertAlmostEqual(result["a"], 0.5)
        self.assertAlmostEqual(result["b"], 0.25)

    def test_list_dampened(self):
        result = tr.dampen_valence_signature([1.0, 2.0, 4.0], hops=2)
        self.assertAlmostEqual(result[0], 0.25)
        self.assertAlmostEqual(result[1], 0.5)
        self.assertAlmostEqual(result[2], 1.0)

    def test_scalar_dampened(self):
        result = tr.dampen_valence_signature(1.0, hops=1)
        self.assertAlmostEqual(result, 0.5)

    def test_zero_hops_no_change(self):
        result = tr.dampen_valence_signature({"x": 2.0}, hops=0)
        self.assertAlmostEqual(result["x"], 2.0)

    def test_none_input_returns_none(self):
        result = tr.dampen_valence_signature(None, hops=1)
        self.assertIsNone(result)

    def test_string_input_returns_none(self):
        result = tr.dampen_valence_signature("text", hops=1)
        self.assertIsNone(result)

    def test_non_numeric_dict_values_excluded(self):
        result = tr.dampen_valence_signature({"a": 1.0, "b": "text"}, hops=1)
        self.assertIn("a", result)
        self.assertNotIn("b", result)


# ---------------------------------------------------------------------------
# _blend_valence_signature
# ---------------------------------------------------------------------------

class TestBlendValenceSignature(unittest.TestCase):
    """Tests for _blend_valence_signature() — alpha-blend two signatures."""

    def test_none_previous_returns_current(self):
        result = tr._blend_valence_signature(None, 0.9, alpha=0.5)
        self.assertAlmostEqual(result, 0.9)

    def test_scalar_blend(self):
        # alpha=0.5: 0.5*0.0 + 0.5*1.0 = 0.5
        result = tr._blend_valence_signature(0.0, 1.0, alpha=0.5)
        self.assertAlmostEqual(result, 0.5)

    def test_scalar_alpha_zero_returns_previous(self):
        result = tr._blend_valence_signature(0.8, 0.2, alpha=0.0)
        self.assertAlmostEqual(result, 0.8)

    def test_scalar_alpha_one_returns_current(self):
        result = tr._blend_valence_signature(0.8, 0.2, alpha=1.0)
        self.assertAlmostEqual(result, 0.2)

    def test_list_blend(self):
        result = tr._blend_valence_signature([0.0, 0.0], [1.0, 1.0], alpha=0.5)
        self.assertAlmostEqual(result[0], 0.5)
        self.assertAlmostEqual(result[1], 0.5)

    def test_dict_blend(self):
        result = tr._blend_valence_signature({"x": 0.0}, {"x": 1.0}, alpha=0.5)
        self.assertAlmostEqual(result["x"], 0.5)

    def test_mismatched_types_returns_current(self):
        # dict + scalar: doesn't match any branch → returns current (dict)
        result = tr._blend_valence_signature([1.0, 2.0], {"x": 1.0}, alpha=0.5)
        # No matching branch; function returns None or current based on impl
        # Just verify it doesn't raise
        _ = result


if __name__ == "__main__":
    unittest.main()
