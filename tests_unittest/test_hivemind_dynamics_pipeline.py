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

from hivemind.dynamics_pipeline import TactiDynamicsPipeline  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()

