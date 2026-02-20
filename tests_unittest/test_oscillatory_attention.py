import os
import unittest

from workspace.tacti_cr.oscillatory_gating import PhaseScheduler


class TestOscillatoryAttention(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_deterministic_phase_progression_and_mutual_exclusion(self):
        os.environ["OPENCLAW_OSCILLATORY_ATTENTION"] = "1"
        scheduler = PhaseScheduler(phase_len=2)
        expected = [
            {"collapse_detect", "collapse_repair"},
            {"collapse_detect", "collapse_repair"},
            {"dream_consolidation", "knowledge_graph"},
            {"dream_consolidation", "knowledge_graph"},
            {"peer_graph_updates"},
            {"peer_graph_updates"},
        ]
        observed = [scheduler.active_subsystems(step) for step in range(6)]
        self.assertEqual(observed, expected)

        for step in range(6):
            active = scheduler.active_subsystems(step)
            total_true = sum(
                1
                for subsystem in ["collapse_detect", "collapse_repair", "dream_consolidation", "knowledge_graph", "peer_graph_updates"]
                if scheduler.should_run(subsystem, step)
            )
            self.assertEqual(total_true, len(active))

    def test_flag_off_runs_all_subsystems(self):
        os.environ["OPENCLAW_OSCILLATORY_ATTENTION"] = "0"
        scheduler = PhaseScheduler(phase_len=3)
        for subsystem in ["collapse_detect", "collapse_repair", "dream_consolidation", "knowledge_graph", "peer_graph_updates"]:
            self.assertTrue(scheduler.should_run(subsystem, step=4))


if __name__ == "__main__":
    unittest.main()
