import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.cross_timescale import CrossTimescaleController  # noqa: E402


class TestTactiCRCrossTimescale(unittest.TestCase):
    def test_reflex_selected_for_short_question(self):
        ctl = CrossTimescaleController()
        out = ctl.process("Status?", recent_failures=0)
        self.assertEqual(out.meta.selected_layer, "reflex")
        self.assertEqual(out.reflex.action, "quick_answer")

    def test_deliberative_selected_for_complex_input(self):
        ctl = CrossTimescaleController()
        task = " ".join(
            [
                "analyze security regression integration architecture debug traceback",
                "constraints fail-closed verify routing failure incident",
            ]
            * 20
        )
        out = ctl.process(task, recent_failures=0)
        self.assertEqual(out.meta.selected_layer, "deliberative")
        self.assertIn("run_risk_review", out.deliberative.plan_steps)

    def test_meta_forces_deliberative_on_failure_mode(self):
        ctl = CrossTimescaleController()
        out = ctl.process("Status?", recent_failures=3)
        self.assertEqual(out.meta.selected_layer, "deliberative")
        self.assertTrue(out.meta.requires_review)


if __name__ == "__main__":
    unittest.main()
