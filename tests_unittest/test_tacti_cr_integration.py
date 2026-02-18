import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.arousal import detect_arousal, get_compute_allocation, ArousalLevel  # noqa: E402
from tacti_cr.temporal import TemporalMemory  # noqa: E402
from tacti_cr.collapse import CollapseDetector  # noqa: E402
from tacti_cr.repair import RepairEngine  # noqa: E402
from tacti_cr.hivemind_bridge import MemoryEntry  # noqa: E402


class TestTactiCRIntegration(unittest.TestCase):
    @patch("tacti_cr.temporal.hivemind_store", return_value=True)
    @patch("tacti_cr.temporal.hivemind_query")
    @patch("tacti_cr.collapse.hivemind_query")
    def test_arousal_temporal_collapse_repair_flow(self, mock_collapse_query, mock_temporal_query, _mock_temporal_store):
        now = datetime(2026, 2, 18, tzinfo=timezone.utc)
        mock_temporal_query.return_value = [
            MemoryEntry(
                kind="incident",
                source="hivemind",
                agent_scope="main",
                score=8,
                created_at=now.isoformat(),
                content="Historical timeout incident with fallback recovery",
                metadata={},
            )
        ]
        mock_collapse_query.return_value = [
            MemoryEntry(
                kind="incident",
                source="hivemind",
                agent_scope="main",
                score=7,
                created_at=now.isoformat(),
                content="all models failed event from prior session",
                metadata={},
            )
        ]

        task = " ".join(
            [
                "analyze routing regression with strict fail-closed constraints",
                "debug timeout incident and verify recovery gates",
            ]
            * 8
        )

        arousal = detect_arousal(task)
        plan = get_compute_allocation(arousal)
        self.assertIn(arousal.level, {ArousalLevel.MEDIUM, ArousalLevel.HIGH})
        self.assertIn(plan.model_tier, {"balanced", "premium"})

        temporal = TemporalMemory(agent_scope="main", sync_hivemind=True)
        temporal.store("Current timeout incident and attempted fallback", importance=0.9, timestamp=now)
        retrieved = temporal.retrieve("timeout fallback", include_hivemind=True, limit=5, now=now)
        self.assertTrue(any("historical timeout incident" in r.content.lower() for r in retrieved))

        collapse = CollapseDetector(agent_scope="main", use_hivemind=True)
        collapse.record_event("provider timeout error")
        collapse.record_event("all models failed after fallback")
        health = collapse.check_health()
        self.assertIn(health.status, {"degraded", "collapse", "healthy"})

        repair = RepairEngine()
        action = repair.repair("operation aborted due to timeout")
        self.assertEqual(action.action, "retry_with_backoff")
        self.assertTrue(action.retryable)


if __name__ == "__main__":
    unittest.main()
