import os
import unittest

from workspace.hivemind.hivemind.active_inference import replay_counterfactuals


class TestActiveInferenceCounterfactual(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_flag_off_yields_no_updates(self):
        os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = "0"
        out = replay_counterfactuals({"provider": "groq", "candidates": ["groq", "ollama"]}, k=3, rng_seed=7)
        self.assertTrue(out["ok"])
        self.assertFalse(out["enabled"])
        self.assertEqual(out["updates"], [])

    def test_flag_on_applies_k_counterfactual_updates(self):
        os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = "1"
        out = replay_counterfactuals(
            {
                "provider": "groq",
                "candidates": ["groq", "ollama", "local_vllm_assistant"],
                "provider_priors": {"ollama": 0.8, "local_vllm_assistant": 0.7},
                "free_energy": {"ollama": 0.4, "local_vllm_assistant": 0.5},
            },
            k=2,
            rng_seed=9,
        )
        self.assertTrue(out["enabled"])
        self.assertEqual(len(out["counterfactuals"]), 2)
        self.assertEqual(len(out["updates"]), 2)

    def test_deterministic_with_fixed_seed(self):
        os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = "1"
        event = {
            "provider": "groq",
            "candidates": ["groq", "ollama", "local_vllm_assistant"],
            "provider_priors": {"ollama": 0.8, "local_vllm_assistant": 0.7},
            "free_energy": {"ollama": 0.4, "local_vllm_assistant": 0.5},
        }
        first = replay_counterfactuals(event, k=3, rng_seed=42)
        second = replay_counterfactuals(event, k=3, rng_seed=42)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
