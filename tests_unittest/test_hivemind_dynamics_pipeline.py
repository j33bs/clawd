import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.dynamics_pipeline import TactiDynamicsPipeline, _env_int, _norm  # noqa: E402
from hivemind.trails import TrailStore  # noqa: E402


class TestTactiDynamicsPipeline(unittest.TestCase):
    def test_plan_consult_order_is_deterministic_with_seed(self):
        with tempfile.TemporaryDirectory() as td:
            trails = TrailStore(path=Path(td) / "trails.jsonl")
            flags = {
                "ENABLE_MURMURATION": "1",
                "ENABLE_RESERVOIR": "1",
                "ENABLE_PHYSARUM_ROUTER": "1",
                "ENABLE_TRAIL_MEMORY": "1",
            }
            with patch.dict(os.environ, flags, clear=False):
                p1 = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude-code"], seed=22, trail_store=trails)
                p2 = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude-code"], seed=22, trail_store=trails)
                r1 = p1.plan_consult_order(
                    source_agent="main",
                    target_intent="memory_query",
                    context_text="routing failure triage",
                    candidate_agents=["codex", "claude-code"],
                )
                r2 = p2.plan_consult_order(
                    source_agent="main",
                    target_intent="memory_query",
                    context_text="routing failure triage",
                    candidate_agents=["codex", "claude-code"],
                )
                self.assertEqual(r1["consult_order"], r2["consult_order"])

    def test_trail_feedback_biases_order(self):
        with tempfile.TemporaryDirectory() as td:
            trails = TrailStore(path=Path(td) / "trails.jsonl")
            with patch.dict(
                os.environ,
                {
                    "ENABLE_MURMURATION": "1",
                    "ENABLE_RESERVOIR": "1",
                    "ENABLE_PHYSARUM_ROUTER": "1",
                    "ENABLE_TRAIL_MEMORY": "1",
                },
                clear=False,
            ):
                pipeline = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude-code"], seed=3, trail_store=trails)
                pipeline.observe_outcome(
                    source_agent="main",
                    path=["main", "codex"],
                    success=True,
                    latency=30,
                    tokens=120,
                    reward=1.2,
                    context_text="routing incident",
                )
                plan = pipeline.plan_consult_order(
                    source_agent="main",
                    target_intent="memory_query",
                    context_text="routing incident",
                    candidate_agents=["codex", "claude-code"],
                )
                self.assertEqual(plan["consult_order"][0], "codex")

    def test_valence_signal_flows_to_physarum_update(self):
        with tempfile.TemporaryDirectory() as td:
            trails = TrailStore(path=Path(td) / "trails.jsonl")
            with patch.dict(
                os.environ,
                {
                    "ENABLE_MURMURATION": "1",
                    "ENABLE_RESERVOIR": "0",
                    "ENABLE_PHYSARUM_ROUTER": "1",
                    "ENABLE_TRAIL_MEMORY": "1",
                    "OPENCLAW_TRAIL_VALENCE": "1",
                },
                clear=False,
            ):
                pipeline = TactiDynamicsPipeline(agent_ids=["main", "codex"], seed=5, trail_store=trails)
                seen = {}

                class _PhysarumStub:
                    def update(self, path, reward_signal, valence=None):
                        seen["path"] = list(path)
                        seen["reward"] = float(reward_signal)
                        seen["valence"] = valence

                    def prune(self, min_k, max_k):
                        seen["prune"] = (int(min_k), int(max_k))

                    def propose_paths(self, source, target, graph, n_paths=3):
                        _ = (source, target, graph, n_paths)
                        return [["main", "codex"]]

                    def snapshot(self):
                        return {}

                pipeline.physarum = _PhysarumStub()
                pipeline.observe_outcome(
                    source_agent="main",
                    path=["main", "codex"],
                    success=True,
                    latency=10,
                    tokens=50,
                    reward=0.8,
                    context_text="route with confidence",
                    valence=0.4,
                )

        self.assertEqual(seen["path"], ["main", "codex"])
        self.assertAlmostEqual(float(seen["valence"]), 0.4, places=6)

    def test_counterfactual_replay_guarded_and_non_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            trails = TrailStore(path=Path(td) / "trails.jsonl")
            with patch.dict(
                os.environ,
                {
                    "ENABLE_MURMURATION": "1",
                    "ENABLE_RESERVOIR": "0",
                    "ENABLE_PHYSARUM_ROUTER": "1",
                    "ENABLE_TRAIL_MEMORY": "1",
                    "OPENCLAW_COUNTERFACTUAL_REPLAY": "1",
                },
                clear=False,
            ):
                with patch("hivemind.dynamics_pipeline.replay_counterfactuals") as replay:
                    replay.return_value = {
                        "ok": True,
                        "enabled": True,
                        "counterfactuals": [{"provider": "codex", "estimated_success": 0.9}],
                    }
                    pipeline = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude-code"], seed=4, trail_store=trails)
                    plan = pipeline.plan_consult_order(
                        source_agent="main",
                        target_intent="memory_query",
                        context_text="route this",
                        candidate_agents=["codex", "claude-code"],
                    )
                    self.assertTrue(plan["counterfactual"]["enabled"])
                    self.assertTrue(plan["counterfactual"]["applied"])

                with patch("hivemind.dynamics_pipeline.replay_counterfactuals", side_effect=RuntimeError("boom")):
                    pipeline = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude-code"], seed=4, trail_store=trails)
                    for _ in range(4):
                        plan = pipeline.plan_consult_order(
                            source_agent="main",
                            target_intent="memory_query",
                            context_text="route this",
                            candidate_agents=["codex", "claude-code"],
                        )
                    self.assertIn(plan["counterfactual"]["reason"], {"error", "temporarily_disabled"})


class TestEnvInt(unittest.TestCase):
    """Tests for dynamics_pipeline._env_int() — env var to int with default."""

    def test_env_var_parsed(self):
        with patch.dict(os.environ, {"SOME_TEST_INT": "42"}, clear=False):
            result = _env_int("SOME_TEST_INT", 0)
            self.assertEqual(result, 42)

    def test_missing_returns_default(self):
        os.environ.pop("SOME_TEST_INT_MISSING", None)
        result = _env_int("SOME_TEST_INT_MISSING", 7)
        self.assertEqual(result, 7)

    def test_invalid_string_returns_default(self):
        with patch.dict(os.environ, {"SOME_TEST_INT": "notanint"}, clear=False):
            result = _env_int("SOME_TEST_INT", 99)
            self.assertEqual(result, 99)

    def test_returns_int(self):
        result = _env_int("SOME_TEST_INT_MISSING_99", 5)
        self.assertIsInstance(result, int)

    def test_float_string_truncated_to_int(self):
        # "3.7" → int("3.7") fails → returns default; NOT converted via float()
        with patch.dict(os.environ, {"SOME_TEST_INT": "3.7"}, clear=False):
            result = _env_int("SOME_TEST_INT", 0)
            self.assertEqual(result, 0)


class TestNorm(unittest.TestCase):
    """Tests for dynamics_pipeline._norm() — min-max normalization."""

    def test_empty_returns_empty(self):
        self.assertEqual(_norm({}), {})

    def test_all_same_values_become_point_five(self):
        result = _norm({"a": 3.0, "b": 3.0, "c": 3.0})
        for v in result.values():
            self.assertAlmostEqual(v, 0.5)

    def test_min_maps_to_zero(self):
        result = _norm({"lo": 0.0, "hi": 10.0})
        self.assertAlmostEqual(result["lo"], 0.0)

    def test_max_maps_to_one(self):
        result = _norm({"lo": 0.0, "hi": 10.0})
        self.assertAlmostEqual(result["hi"], 1.0)

    def test_midpoint_maps_to_half(self):
        result = _norm({"lo": 0.0, "mid": 5.0, "hi": 10.0})
        self.assertAlmostEqual(result["mid"], 0.5)

    def test_keys_preserved(self):
        result = _norm({"alpha": 1.0, "beta": 3.0})
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_returns_dict(self):
        self.assertIsInstance(_norm({"a": 1.0}), dict)


if __name__ == "__main__":
    unittest.main()
