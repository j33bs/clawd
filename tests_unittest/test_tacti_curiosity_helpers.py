"""Tests for pure helpers in workspace/tacti/curiosity.py.

Pure stdlib (no imports beyond typing) — no stubs needed.
Loads via real workspace.tacti package.

Covers:
- epistemic_value() — reads action dict keys
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.tacti.curiosity import epistemic_value


# ---------------------------------------------------------------------------
# epistemic_value
# ---------------------------------------------------------------------------

class TestEpistemicValue(unittest.TestCase):
    """Tests for epistemic_value() — lightweight EFE epistemic component."""

    def test_returns_float(self):
        result = epistemic_value({}, {})
        self.assertIsInstance(result, float)

    def test_zero_for_empty_action(self):
        result = epistemic_value({}, {})
        self.assertAlmostEqual(result, 0.0)

    def test_reads_epistemic_value_key(self):
        action = {"epistemic_value": 0.8}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, 0.8)

    def test_epistemic_value_takes_priority(self):
        """If both keys present, epistemic_value key wins."""
        action = {"epistemic_value": 0.5, "uncertainty_delta": 0.9}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, 0.5)

    def test_falls_back_to_uncertainty_delta(self):
        action = {"uncertainty_delta": 0.3}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, 0.3)

    def test_state_is_ignored(self):
        """state parameter is not used in the computation."""
        action = {"epistemic_value": 1.0}
        r1 = epistemic_value({"x": 1}, action)
        r2 = epistemic_value({"x": 99, "y": "z"}, action)
        self.assertAlmostEqual(r1, r2)

    def test_coerces_to_float(self):
        """String-compatible numeric values are coerced via float()."""
        action = {"epistemic_value": "0.42"}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, 0.42)

    def test_handles_none_uncertainty_delta(self):
        """Missing key → float(action.get(..., 0.0)) = 0.0."""
        action = {}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, 0.0)

    def test_negative_value_returned(self):
        action = {"epistemic_value": -0.5}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, -0.5)

    def test_large_value_passed_through(self):
        action = {"epistemic_value": 999.9}
        result = epistemic_value({}, action)
        self.assertAlmostEqual(result, 999.9)


if __name__ == "__main__":
    unittest.main()
