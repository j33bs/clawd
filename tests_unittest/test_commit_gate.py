"""Tests for commit_gate — cosine_distance, check_isolation, check_constraints, JOINT_PATTERN."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "workspace" / "tools"
STORE_DIR = REPO_ROOT / "workspace" / "store"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(STORE_DIR) not in sys.path:
    sys.path.insert(0, str(STORE_DIR))

import commit_gate as cg


class TestCosineDistance(unittest.TestCase):
    """Tests for cosine_distance() — 1 - cosine_similarity, range [0, 2]."""

    def test_identical_vectors_return_zero(self):
        a = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cg.cosine_distance(a, a), 0.0, places=6)

    def test_orthogonal_vectors_return_one(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(cg.cosine_distance(a, b), 1.0, places=6)

    def test_opposite_vectors_return_two(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        self.assertAlmostEqual(cg.cosine_distance(a, b), 2.0, places=6)

    def test_zero_vector_returns_one(self):
        # Per implementation: norm==0 → return 1.0
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cg.cosine_distance(a, b), 1.0, places=6)

    def test_both_zero_vectors_return_one(self):
        a = [0.0, 0.0]
        self.assertAlmostEqual(cg.cosine_distance(a, a), 1.0, places=6)

    def test_symmetric(self):
        a = [0.5, 0.8, 0.2]
        b = [0.1, 0.9, 0.4]
        self.assertAlmostEqual(cg.cosine_distance(a, b), cg.cosine_distance(b, a), places=6)

    def test_partial_overlap(self):
        # 45-degree vectors → distance = 1 - cos(45) ≈ 0.293
        import math
        a = [1.0, 0.0]
        b = [math.sqrt(0.5), math.sqrt(0.5)]
        dist = cg.cosine_distance(a, b)
        self.assertAlmostEqual(dist, 1.0 - math.cos(math.pi / 4), places=5)

    def test_scaled_vector_same_distance(self):
        # Scaling does not change cosine distance
        a = [1.0, 2.0]
        b = [2.0, 4.0]  # 2*a
        self.assertAlmostEqual(cg.cosine_distance(a, b), 0.0, places=6)

    def test_distance_non_negative(self):
        import random
        rng = random.Random(7)
        a = [rng.uniform(-1, 1) for _ in range(10)]
        b = [rng.uniform(-1, 1) for _ in range(10)]
        self.assertGreaterEqual(cg.cosine_distance(a, b), -1e-9)

    def test_distance_at_most_two(self):
        a = [1.0, 0.0]
        b = [-1.0, -1e-9]
        self.assertLessEqual(cg.cosine_distance(a, b), 2.0 + 1e-9)


class TestCheckIsolation(unittest.TestCase):
    """Tests for check_isolation() — XCV Amendment A attestation."""

    def test_empty_string_returns_not_verified(self):
        result = cg.check_isolation("")
        self.assertFalse(result["isolation_verified"])

    def test_whitespace_only_returns_not_verified(self):
        result = cg.check_isolation("   ")
        self.assertFalse(result["isolation_verified"])

    def test_none_returns_not_verified(self):
        result = cg.check_isolation(None)  # type: ignore
        self.assertFalse(result["isolation_verified"])

    def test_valid_evidence_returns_verified(self):
        evidence = "c_lawd session: 21:04Z, dali session: 21:07Z, no overlap"
        result = cg.check_isolation(evidence)
        self.assertTrue(result["isolation_verified"])

    def test_evidence_is_stripped(self):
        result = cg.check_isolation("  evidence here  ")
        self.assertEqual(result["isolation_evidence"], "evidence here")

    def test_empty_evidence_has_error_field(self):
        result = cg.check_isolation("")
        self.assertIn("error", result)

    def test_empty_evidence_field_empty(self):
        result = cg.check_isolation("")
        self.assertEqual(result["isolation_evidence"], "")

    def test_valid_includes_evidence_in_result(self):
        ev = "sessions did not overlap: c_lawd 09:00Z, Dali 09:30Z"
        result = cg.check_isolation(ev)
        self.assertEqual(result["isolation_evidence"], ev)


class TestCheckConstraints(unittest.TestCase):
    """Tests for check_constraints() — XCV Amendment C constraint check."""

    def test_no_constraints_returns_skipped(self):
        result = cg.check_constraints("some joint text", None, None)
        self.assertEqual(result["constraint_check"], "skipped")

    def test_both_empty_strings_returns_skipped(self):
        result = cg.check_constraints("text", "", "")
        # "" is falsy → no constraints
        self.assertEqual(result["constraint_check"], "skipped")

    def test_one_constraint_returns_pending(self):
        result = cg.check_constraints("joint text", "preserve provenance", None)
        self.assertEqual(result["constraint_check"], "pending_human_review")

    def test_both_constraints_returns_pending(self):
        result = cg.check_constraints("joint text", "preserve provenance", "max 200 tokens")
        self.assertEqual(result["constraint_check"], "pending_human_review")

    def test_constraints_recorded_in_result(self):
        result = cg.check_constraints("text", "c_lawd constraint", "dali constraint")
        self.assertEqual(result["c_lawd_constraint"], "c_lawd constraint")
        self.assertEqual(result["dali_constraint"], "dali constraint")

    def test_missing_constraint_shown_as_not_supplied(self):
        result = cg.check_constraints("text", "c_lawd only", None)
        self.assertIn("not supplied", result["dali_constraint"])

    def test_joint_output_length_counted(self):
        joint = "word " * 50  # 50 words
        result = cg.check_constraints(joint.strip(), "c", "d")
        self.assertEqual(result["joint_output_length_tokens"], 50)

    def test_instruction_field_present_when_pending(self):
        result = cg.check_constraints("text", "c", "d")
        self.assertIn("instruction", result)
        self.assertIn("review", result["instruction"].lower())

    def test_reason_in_skipped_result(self):
        result = cg.check_constraints("text", None, None)
        self.assertIn("reason", result)


class TestJointPattern(unittest.TestCase):
    """Tests for JOINT_PATTERN — Safeguard 2 (XCIV) prefix matching."""

    def test_exact_prefix_matches(self):
        text = "[JOINT: c_lawd + Dali] some content"
        self.assertIsNotNone(cg.JOINT_PATTERN.match(text))

    def test_case_insensitive_match(self):
        text = "[joint: c_lawd + dali] some content"
        self.assertIsNotNone(cg.JOINT_PATTERN.match(text))

    def test_extra_spaces_match(self):
        text = "[JOINT:  c_lawd  +  Dali] content"
        self.assertIsNotNone(cg.JOINT_PATTERN.match(text))

    def test_missing_prefix_no_match(self):
        text = "Some content without the prefix"
        self.assertIsNone(cg.JOINT_PATTERN.match(text))

    def test_prefix_with_leading_whitespace_no_match(self):
        # Leading whitespace prevents .match() from finding the prefix at position 0
        text = " [JOINT: c_lawd + Dali] content"
        self.assertIsNone(cg.JOINT_PATTERN.match(text))

    def test_stripped_whitespace_does_match(self):
        # Same text, but stripped — prefix is at position 0, should match
        text = " [JOINT: c_lawd + Dali] content"
        self.assertIsNotNone(cg.JOINT_PATTERN.match(text.strip()))

    def test_partial_prefix_no_match(self):
        text = "[JOINT: c_lawd]"
        self.assertIsNone(cg.JOINT_PATTERN.match(text))

    def test_joint_constant_itself_matches(self):
        self.assertIsNotNone(cg.JOINT_PATTERN.match(cg.JOINT_PREFIX))


if __name__ == "__main__":
    unittest.main()
