import os
import unittest

from workspace.tacti_cr.temporal import TemporalMemory, surprise_score_proxy, text_embedding_proxy


class TestTemporalSurpriseGate(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_flag_on_blocks_low_kl_and_allows_high_kl(self):
        os.environ["OPENCLAW_TEMPORAL_SURPRISE_GATE"] = "1"
        mem = TemporalMemory(sync_hivemind=False)
        centroid = text_embedding_proxy("known stable routing event")

        low = mem.store(
            "known stable routing event",
            metadata={"reservoir_centroid": centroid, "surprise_threshold": 0.05},
        )
        high = mem.store(
            "zxqv anomaly witness contradiction",
            metadata={"reservoir_centroid": centroid, "surprise_threshold": 0.05},
        )

        self.assertEqual(low.metadata.get("surprise_blocked"), "1")
        self.assertNotEqual(high.metadata.get("surprise_blocked"), "1")
        self.assertEqual(mem.size, 1)

    def test_flag_off_keeps_both_entries(self):
        os.environ["OPENCLAW_TEMPORAL_SURPRISE_GATE"] = "0"
        mem = TemporalMemory(sync_hivemind=False)
        centroid = text_embedding_proxy("known stable routing event")
        mem.store("known stable routing event", metadata={"reservoir_centroid": centroid, "surprise_threshold": 0.05})
        mem.store("zxqv anomaly witness contradiction", metadata={"reservoir_centroid": centroid, "surprise_threshold": 0.05})
        self.assertEqual(mem.size, 2)

    def test_threshold_adaptation_updates_ema_deterministically(self):
        os.environ["OPENCLAW_TEMPORAL_SURPRISE_GATE"] = "1"
        mem = TemporalMemory(sync_hivemind=False)
        centroid = text_embedding_proxy("known stable routing event")
        s1 = surprise_score_proxy("known stable routing event", centroid)
        s2 = surprise_score_proxy("zxqv anomaly witness contradiction", centroid)

        mem.store(
            "known stable routing event",
            metadata={"reservoir_centroid": centroid, "surprise_floor": 0.01, "surprise_mult": 1.0, "surprise_ema_alpha": 0.5},
        )
        mem.store(
            "zxqv anomaly witness contradiction",
            metadata={"reservoir_centroid": centroid, "surprise_floor": 0.01, "surprise_mult": 1.0, "surprise_ema_alpha": 0.5},
        )
        self.assertAlmostEqual(mem._surprise_ema, ((s1 * 0.5) + (s2 * 0.5)), places=6)


if __name__ == "__main__":
    unittest.main()
