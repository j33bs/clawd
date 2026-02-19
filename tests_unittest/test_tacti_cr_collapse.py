import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.collapse import CollapseDetector  # noqa: E402


class TestTactiCRCollapse(unittest.TestCase):
    def test_health_is_healthy_by_default(self):
        detector = CollapseDetector()
        state = detector.check_health()
        self.assertEqual(state.status, "healthy")
        self.assertEqual(state.recommended_actions, [])

    def test_degraded_detects_repeated_failures(self):
        detector = CollapseDetector()
        for _ in range(3):
            detector.record_event("provider timeout error")
        state = detector.check_health()
        self.assertEqual(state.status, "degraded")
        self.assertIn("repeated_failures", state.warnings)

    def test_collapse_state_on_severe_failure_count(self):
        detector = CollapseDetector()
        for _ in range(6):
            detector.record_event("request failed with error")
        state = detector.check_health()
        self.assertEqual(state.status, "collapse")
        self.assertIn("trip_circuit_breaker", state.recommended_actions)

    def test_provider_exhaustion_warning_when_last_event_matches(self):
        detector = CollapseDetector()
        detector.record_event("minor retry")
        detector.record_event("all models failed after fallback")
        warnings = detector.detect_collapse_precursors()
        self.assertIn("provider_exhaustion", warnings)

    @patch("tacti_cr.collapse.hivemind_query")
    def test_hivemind_history_adds_warning_and_action(self, mock_query):
        from tacti_cr.hivemind_bridge import MemoryEntry

        mock_query.return_value = [
            MemoryEntry(
                kind="incident",
                source="manual",
                agent_scope="main",
                score=5,
                created_at="2026-02-18T00:00:00+00:00",
                content="past all models failed incident",
                metadata={},
            )
        ]
        detector = CollapseDetector(use_hivemind=True)
        for _ in range(3):
            detector.record_event("provider timeout error")
        state = detector.check_health()
        self.assertEqual(state.status, "degraded")
        self.assertIn("historical_incidents_found", state.warnings)
        self.assertIn("review_hivemind_incidents", state.recommended_actions)


if __name__ == "__main__":
    unittest.main()
