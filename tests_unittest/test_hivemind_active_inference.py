import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.active_inference import (  # noqa: E402
    PreferenceModel, _clamp01, PredictionError, generate_counterfactual_routings,
)


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


class TestClamp01(unittest.TestCase):
    """Tests for active_inference._clamp01() — [0,1] clamping."""

    def test_below_zero_clamped(self):
        self.assertAlmostEqual(_clamp01(-5.0), 0.0)

    def test_above_one_clamped(self):
        self.assertAlmostEqual(_clamp01(2.0), 1.0)

    def test_within_range_unchanged(self):
        self.assertAlmostEqual(_clamp01(0.5), 0.5)

    def test_exactly_zero(self):
        self.assertAlmostEqual(_clamp01(0.0), 0.0)

    def test_exactly_one(self):
        self.assertAlmostEqual(_clamp01(1.0), 1.0)

    def test_returns_float(self):
        self.assertIsInstance(_clamp01(0.5), float)


class TestPredictionError(unittest.TestCase):
    """Tests for active_inference.PredictionError.compute()."""

    def test_identical_dicts_return_zero(self):
        pred = {"a": 0.5, "b": 0.8}
        obs = {"a": 0.5, "b": 0.8}
        self.assertAlmostEqual(PredictionError.compute(pred, obs), 0.0)

    def test_no_shared_keys_returns_one(self):
        pred = {"x": 0.5}
        obs = {"y": 0.5}
        self.assertAlmostEqual(PredictionError.compute(pred, obs), 1.0)

    def test_single_key_error(self):
        pred = {"a": 0.0}
        obs = {"a": 1.0}
        self.assertAlmostEqual(PredictionError.compute(pred, obs), 1.0)

    def test_partial_overlap_averages_shared(self):
        pred = {"a": 0.0, "b": 1.0}  # only "a" is shared
        obs = {"a": 0.5, "z": 9.9}
        result = PredictionError.compute(pred, obs)
        self.assertAlmostEqual(result, 0.5, places=5)

    def test_returns_float(self):
        self.assertIsInstance(PredictionError.compute({"a": 1.0}, {"a": 0.5}), float)


class TestGenerateCounterfactualRoutings(unittest.TestCase):
    """Tests for generate_counterfactual_routings() — disabled by default."""

    def test_returns_empty_when_disabled(self):
        # OPENCLAW_AIF_COUNTERFACTUAL not set → disabled by default
        result = generate_counterfactual_routings({"provider": "openai"})
        self.assertEqual(result, [])

    def test_returns_list(self):
        result = generate_counterfactual_routings({})
        self.assertIsInstance(result, list)

    def test_returns_list_type(self):
        result = generate_counterfactual_routings({"provider": "test"})
        self.assertIsInstance(result, list)

    def test_enabled_returns_non_empty(self):
        import os
        old = os.environ.get("OPENCLAW_AIF_COUNTERFACTUAL")
        os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = "1"
        try:
            result = generate_counterfactual_routings(
                {"provider": "openai", "reason_code": "timeout"},
                candidates=["openai", "groq"],
            )
            self.assertGreater(len(result), 0)
            self.assertIn("provider", result[0])
            self.assertIn("estimated_success", result[0])
        finally:
            if old is None:
                os.environ.pop("OPENCLAW_AIF_COUNTERFACTUAL", None)
            else:
                os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = old

    def test_enabled_score_in_unit_interval(self):
        import os
        old = os.environ.get("OPENCLAW_AIF_COUNTERFACTUAL")
        os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = "1"
        try:
            result = generate_counterfactual_routings(
                {"provider": "groq"}, candidates=["groq", "ollama"],
            )
            for item in result:
                self.assertGreaterEqual(item["estimated_success"], 0.0)
                self.assertLessEqual(item["estimated_success"], 1.0)
        finally:
            if old is None:
                os.environ.pop("OPENCLAW_AIF_COUNTERFACTUAL", None)
            else:
                os.environ["OPENCLAW_AIF_COUNTERFACTUAL"] = old


if __name__ == "__main__":
    unittest.main()

