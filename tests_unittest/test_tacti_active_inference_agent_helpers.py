"""Tests for pure helpers in workspace/tacti/active_inference_agent.py.

Uses real workspace.tacti package (no stubs needed — efe_calculator is real).

Covers:
- ActiveInferenceAgent.__init__ (dataclass defaults)
- ActiveInferenceAgent.step (noop path, policy selection)
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.tacti.active_inference_agent import ActiveInferenceAgent


# ---------------------------------------------------------------------------
# __init__ / dataclass defaults
# ---------------------------------------------------------------------------

class TestActiveInferenceAgentInit(unittest.TestCase):
    """Tests for ActiveInferenceAgent dataclass defaults."""

    def test_creates_instance(self):
        agent = ActiveInferenceAgent()
        self.assertIsInstance(agent, ActiveInferenceAgent)

    def test_beliefs_defaults_to_empty_dict(self):
        agent = ActiveInferenceAgent()
        self.assertEqual(agent.beliefs, {})

    def test_model_defaults_to_empty_dict(self):
        agent = ActiveInferenceAgent()
        self.assertEqual(agent.model, {})

    def test_custom_beliefs_set(self):
        agent = ActiveInferenceAgent(beliefs={"arousal": 0.7})
        self.assertEqual(agent.beliefs["arousal"], 0.7)

    def test_custom_model_set(self):
        agent = ActiveInferenceAgent(model={"utility_weight": 2.0})
        self.assertEqual(agent.model["utility_weight"], 2.0)

    def test_different_instances_independent_beliefs(self):
        a1 = ActiveInferenceAgent()
        a2 = ActiveInferenceAgent()
        a1.beliefs["x"] = 1
        self.assertNotIn("x", a2.beliefs)


# ---------------------------------------------------------------------------
# step
# ---------------------------------------------------------------------------

class TestActiveInferenceAgentStep(unittest.TestCase):
    """Tests for ActiveInferenceAgent.step()."""

    def test_returns_dict(self):
        agent = ActiveInferenceAgent()
        result = agent.step({"candidate_policies": [{"expected_utility": 1.0}]})
        self.assertIsInstance(result, dict)

    def test_noop_when_no_candidate_policies(self):
        agent = ActiveInferenceAgent()
        result = agent.step({})
        self.assertEqual(result["type"], "noop")

    def test_noop_when_empty_candidate_policies(self):
        agent = ActiveInferenceAgent()
        result = agent.step({"candidate_policies": []})
        self.assertEqual(result["type"], "noop")

    def test_noop_reason_set(self):
        agent = ActiveInferenceAgent()
        result = agent.step({})
        self.assertIn("reason", result)
        self.assertEqual(result["reason"], "no_candidate_policies")

    def test_policy_type_when_candidates_present(self):
        agent = ActiveInferenceAgent()
        policies = [{"expected_utility": 0.5}]
        result = agent.step({"candidate_policies": policies})
        self.assertEqual(result["type"], "policy")

    def test_returns_highest_scored_policy(self):
        agent = ActiveInferenceAgent()
        policies = [
            {"expected_utility": 0.1, "name": "low"},
            {"expected_utility": 0.9, "name": "high"},
        ]
        result = agent.step({"candidate_policies": policies})
        self.assertEqual(result["policy"]["expected_utility"], 0.9)

    def test_returns_score(self):
        agent = ActiveInferenceAgent()
        policies = [{"expected_utility": 0.5}]
        result = agent.step({"candidate_policies": policies})
        self.assertIn("score", result)
        self.assertIsInstance(result["score"], float)

    def test_updates_beliefs_last_observation(self):
        agent = ActiveInferenceAgent()
        obs = {"candidate_policies": [{"expected_utility": 0.3}], "ctx": "test"}
        agent.step(obs)
        self.assertIn("last_observation", agent.beliefs)
        self.assertEqual(agent.beliefs["last_observation"]["ctx"], "test")

    def test_noop_when_candidate_policies_not_list(self):
        """candidate_policies must be a list — if not, returns noop."""
        agent = ActiveInferenceAgent()
        result = agent.step({"candidate_policies": "not-a-list"})
        self.assertEqual(result["type"], "noop")

    def test_stateful_beliefs_accumulate(self):
        """Repeated steps update beliefs each time."""
        agent = ActiveInferenceAgent()
        agent.step({"candidate_policies": [{"expected_utility": 0.1}], "round": 1})
        agent.step({"candidate_policies": [{"expected_utility": 0.2}], "round": 2})
        self.assertEqual(agent.beliefs["last_observation"]["round"], 2)


if __name__ == "__main__":
    unittest.main()
