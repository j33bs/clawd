import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import deliberation_store  # noqa: E402


class DeliberationWorldBetterTests(unittest.TestCase):
    def test_deliberation_store_tracks_guardrails_and_quality(self):
        with tempfile.TemporaryDirectory() as td:
            deliberation_root = Path(td) / "deliberations"
            with mock.patch.object(deliberation_store.teamchat_deliberation, "DELIBERATION_PATH", deliberation_root):
                created = deliberation_store.create_deliberation(
                    title="Test cell",
                    prompt="How should Source reduce coordination friction?",
                    mission_task_id="source-001",
                    time_horizon="0-6m",
                    beneficiaries=["users", "operators"],
                    desired_outcome="Reduce repeated explanation.",
                    guardrails=["show provenance"],
                    success_metrics=["shared packet coverage"],
                    risks=["context leak"],
                )
                contribution = deliberation_store.add_contribution(
                    created["id"],
                    agent_id="c_lawd",
                    role="synthesist",
                    content="Unify the packet across surfaces.",
                    evidence_refs=["portfolio:source_mission:source-001"],
                    confidence=0.84,
                    uncertainty="Need more field validation.",
                )
                updated = deliberation_store.add_synthesis(
                    created["id"],
                    synthesis="Ship the shared packet first.",
                    dissent_noted=True,
                    recommended_action="Implement packet schema adoption.",
                    confidence=0.81,
                    guardrails=["show provenance"],
                    success_metrics=["shared packet coverage"],
                )
                loaded = deliberation_store.get_deliberation(created["id"])
                summary = deliberation_store.load_deliberation_summary(limit=4)

        self.assertEqual(contribution["evidence_refs"][0], "portfolio:source_mission:source-001")
        self.assertGreaterEqual(updated["quality"]["score"], 80)
        self.assertEqual(loaded["mission_task_id"], "source-001")
        self.assertGreaterEqual(summary["avg_quality_score"], 80)
        self.assertEqual(loaded["synthesis"]["recommended_action"], "Implement packet schema adoption.")


if __name__ == "__main__":
    unittest.main()
