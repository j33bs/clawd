import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.arousal import (  # noqa: E402
    ArousalLevel,
    detect_arousal,
    get_compute_allocation,
    recommend_tier,
)


class TestTactiCRArousal(unittest.TestCase):
    def test_detect_arousal_low_for_simple_input(self):
        state = detect_arousal("Check QMD status")
        self.assertEqual(state.level, ArousalLevel.LOW)
        self.assertLessEqual(state.score, 0.33)

        plan = get_compute_allocation(state)
        self.assertEqual(plan.model_tier, "fast")
        self.assertFalse(plan.allow_paid)

    def test_detect_arousal_medium_for_moderate_constraints(self):
        task = " ".join(["debug routing integration verify fallback must"] * 12)
        state = detect_arousal(task)

        self.assertEqual(state.level, ArousalLevel.MEDIUM)
        self.assertGreater(state.score, 0.33)
        self.assertLessEqual(state.score, 0.66)

        plan = get_compute_allocation(state)
        self.assertEqual(plan.model_tier, "balanced")
        self.assertEqual(plan.context_budget, 4000)

    def test_detect_arousal_high_for_complex_multistep_input(self):
        task = " ".join(
            [
                "analyze security regression integration architecture debug traceback",
                "constraints fail-closed verify routing failure incident",
            ]
            * 30
        )

        state = detect_arousal(task)
        self.assertEqual(state.level, ArousalLevel.HIGH)
        self.assertGreater(state.score, 0.66)

        plan = get_compute_allocation(state)
        self.assertEqual(plan.model_tier, "premium")
        self.assertTrue(plan.allow_paid)
        self.assertEqual(recommend_tier(task), "premium")


if __name__ == "__main__":
    unittest.main()
