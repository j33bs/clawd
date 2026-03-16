import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))

from api import world_better  # noqa: E402


class WorldBetterPlanningTests(unittest.TestCase):
    def test_build_world_better_payload_scores_tasks_and_phases(self):
        source_mission = {
            "tasks": [
                {
                    "id": "source-001",
                    "title": "Universal Context Packet",
                    "priority": "critical",
                    "status": "in_progress",
                    "summary": "One packet everywhere.",
                    "impact_vector": "continuity",
                    "time_horizon": "0-6m",
                    "beneficiaries": ["users", "operators"],
                    "public_benefit_hypothesis": "Reduce repeated explanation.",
                    "leading_indicators": ["shared packet coverage"],
                    "guardrails": ["show provenance"],
                    "evidence_status": "operational",
                    "reversibility": "high",
                    "leverage": "platform",
                },
                {
                    "id": "source-004",
                    "title": "Personal Inference Graph",
                    "priority": "high",
                    "status": "backlog",
                    "summary": "Structured preferences.",
                    "impact_vector": "personalization",
                    "time_horizon": "6-18m",
                    "beneficiaries": ["users"],
                    "public_benefit_hypothesis": "Reduce repeated prompt stuffing.",
                    "leading_indicators": ["targeted inference packets"],
                    "guardrails": ["reviewable nodes"],
                    "evidence_status": "emerging",
                    "reversibility": "medium",
                    "leverage": "platform",
                },
            ],
            "three_year_outcomes": [{"id": "continuity", "label": "Continuity", "summary": "Less re-explanation."}],
            "anti_goals": ["Reward busyness over beneficial change."],
            "decision_rules": ["Prefer reversible improvements when evidence is thin."],
        }
        deliberations = {"items": [{"quality_score": 75}]}
        weekly_evolution = {"status": "active"}

        payload = world_better.build_world_better_payload(
            source_mission=source_mission,
            tasks=[],
            deliberations=deliberations,
            weekly_evolution=weekly_evolution,
            context_packet={"summary_lines": ["line a", "line b"]},
        )

        self.assertEqual(payload["status"], "active")
        self.assertEqual(payload["scorecard"][0]["value"], "2/2")
        self.assertEqual(payload["top_priorities"][0]["id"], "source-001")
        self.assertEqual(payload["roadmap"]["phases"][0]["time_horizon"], "0-6m")
        self.assertEqual(payload["beneficiary_map"][0]["label"], "operators")
        self.assertEqual(payload["anti_goals"][0], "Reward busyness over beneficial change.")

    def test_build_three_year_roadmap_markdown_renders_priorities(self):
        payload = {
            "summary": "2/2 mission tasks carry public-benefit scaffolding.",
            "scorecard": [
                {"label": "Impact-ready mission tasks", "value": "2/2", "detail": "Complete"},
            ],
            "top_priorities": [
                {
                    "title": "Universal Context Packet",
                    "time_horizon": "0-6m",
                    "impact_score": 92,
                    "why_now": "Reduce repeated explanation.",
                    "guardrails": ["show provenance"],
                    "leading_indicators": ["shared packet coverage"],
                }
            ],
            "roadmap": {
                "phases": [
                    {
                        "label": "Phase 1 - Trust foundations",
                        "objective": "Reduce friction.",
                        "tasks": [
                            {
                                "title": "Universal Context Packet",
                                "summary": "One packet everywhere.",
                                "beneficiaries": ["users"],
                                "guardrails": ["show provenance"],
                            }
                        ],
                    }
                ]
            },
            "anti_goals": ["Reward busyness over beneficial change."],
        }
        markdown = world_better.build_three_year_roadmap_markdown(payload)
        self.assertIn("Source World-Better Roadmap", markdown)
        self.assertIn("Universal Context Packet", markdown)
        self.assertIn("Anti-goals", markdown)


if __name__ == "__main__":
    unittest.main()
