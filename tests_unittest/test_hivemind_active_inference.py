import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.active_inference import PreferenceModel  # noqa: E402


class TestActiveInferenceModel(unittest.TestCase):
    def test_positive_feedback_increases_prior(self):
        model = PreferenceModel()
        start = model.priors["tool_use_tolerance"]
        for _ in range(8):
            model.predict({"input_text": "use tools where needed"})
            model.update(
                feedback={"liked": True, "tool_use_tolerance": 0.95},
                observed_outcome={"tool_score": 0.9},
            )
        self.assertGreater(model.priors["tool_use_tolerance"], start)

    def test_prediction_error_decreases_over_cycles(self):
        model = PreferenceModel()
        errors = []
        for _ in range(10):
            pred, _ = model.predict({"input_text": "concise bullets"})
            observed = {
                "verbosity_score": 0.25,
                "format_score": 0.85,
                "tool_score": 0.65,
                "correction_score": 0.7,
            }
            result = model.update(feedback={"liked": True}, observed_outcome=observed)
            errors.append(float(result["prediction_error"]))
        self.assertGreater(errors[0], errors[-1])

    def test_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            model = PreferenceModel()
            model.predict({"input_text": "detailed"})
            model.update(feedback={"liked": True}, observed_outcome={"verbosity_score": 0.8})
            path = Path(td) / "state.json"
            model.save_path(path)
            self.assertTrue(path.exists())
            loaded = PreferenceModel.load_path(path)
            self.assertEqual(set(model.priors.keys()), set(loaded.priors.keys()))
            self.assertEqual(model.interactions, loaded.interactions)


if __name__ == "__main__":
    unittest.main()

