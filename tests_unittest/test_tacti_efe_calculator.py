import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti.efe_calculator import evaluate  # noqa: E402


class TestTactiEfeCalculator(unittest.TestCase):
    def test_expected_utility_and_epistemic_are_monotonic(self):
        ranked = evaluate(
            policies=[
                {"id": "a", "expected_utility": 0.6, "epistemic_value": 0.2, "complexity": 0.2},
                {"id": "b", "expected_utility": 0.8, "epistemic_value": 0.2, "complexity": 0.2},
                {"id": "c", "expected_utility": 0.8, "epistemic_value": 0.6, "complexity": 0.2},
            ],
            beliefs={"arousal": 0.3, "collapse_mode": False},
            model={"utility_weight": 1.0, "epistemic_weight": 0.6, "arousal_weight": 0.8},
        )
        ordered = [row["policy"]["id"] for row in ranked]
        self.assertEqual(ordered, ["c", "b", "a"])

    def test_arousal_and_collapse_penalize_complex_policies(self):
        ranked = evaluate(
            policies=[
                {"id": "low", "expected_utility": 0.7, "epistemic_value": 0.3, "complexity": 0.2},
                {"id": "high", "expected_utility": 0.7, "epistemic_value": 0.3, "complexity": 0.9},
            ],
            beliefs={"arousal": 0.95, "collapse_mode": True},
            model={"utility_weight": 1.0, "epistemic_weight": 0.6, "arousal_weight": 1.0, "collapse_penalty_weight": 1.2},
        )
        self.assertEqual(ranked[0]["policy"]["id"], "low")
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])


if __name__ == "__main__":
    unittest.main()
