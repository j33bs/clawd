import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

import policy_router  # noqa: E402


class TestPolicyRouterActiveInferenceHook(unittest.TestCase):
    def test_active_inference_predict_and_update_in_execute(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            budget = tmp / "budget.json"
            circuit = tmp / "circuit.json"
            events = tmp / "events.jsonl"
            ai_state = tmp / "active_inference_state.json"
            captured = {}

            def _handler(payload, model_id, context_metadata):
                captured["context_metadata"] = dict(context_metadata)
                return {"ok": True, "text": "- concise bullet output"}

            env = {
                "ENABLE_ACTIVE_INFERENCE": "1",
                "GROQ_API_KEY": "dummy-test-key",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch.object(policy_router, "ACTIVE_INFERENCE_STATE_PATH", ai_state):
                    router = policy_router.PolicyRouter(
                        budget_path=budget,
                        circuit_path=circuit,
                        event_log=events,
                        handlers={"groq": _handler},
                    )
                    result = router.execute_with_escalation(
                        "governance",
                        {"prompt": "be concise and structured"},
                        context_metadata={
                            "input_text": "be concise and structured",
                            "feedback": {"liked": True},
                            "requires_tools": False,
                        },
                    )

            self.assertTrue(result["ok"])
            self.assertIn("active_inference", captured["context_metadata"])
            ai = captured["context_metadata"]["active_inference"]
            self.assertIn("preference_params", ai)
            self.assertIn("confidence", ai)
            self.assertTrue(ai_state.exists())


if __name__ == "__main__":
    unittest.main()
