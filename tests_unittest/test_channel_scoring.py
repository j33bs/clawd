import json
import os
import tempfile
import unittest

from core_infra.channel_scoring import (
    DEFAULT_SCORES, load_channel_scores, validate_scores, _to_float, _list_to_scores,
)


class TestChannelScoring(unittest.TestCase):
    def test_missing_file_returns_defaults(self):
        path = os.path.join(tempfile.gettempdir(), "__no_such_scores__.json")
        out = load_channel_scores(path)
        self.assertEqual(out, DEFAULT_SCORES)

    def test_invalid_json_returns_defaults(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("{not:json")
            path = f.name
        try:
            out = load_channel_scores(path)
            self.assertEqual(out, DEFAULT_SCORES)
        finally:
            os.unlink(path)

    def test_mapping_loads(self):
        data = {"alpha": 0.5, "beta": 1.5}
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            out = load_channel_scores(path, defaults={"alpha": 1.0})
            self.assertEqual(out, data)
        finally:
            os.unlink(path)

    def test_negative_weight_clamped(self):
        scores = validate_scores({"alpha": -1, "beta": 0.2})
        self.assertEqual(scores.get("alpha"), 0.0)
        self.assertEqual(scores.get("beta"), 0.2)


class TestToFloat(unittest.TestCase):
    """Tests for channel_scoring._to_float() — safe float coercion."""

    def test_int_coerced(self):
        self.assertAlmostEqual(_to_float(5), 5.0)

    def test_string_float_coerced(self):
        self.assertAlmostEqual(_to_float("2.5"), 2.5)

    def test_non_numeric_returns_none(self):
        self.assertIsNone(_to_float("bad"))

    def test_none_returns_none(self):
        self.assertIsNone(_to_float(None))

    def test_nan_returns_none(self):
        self.assertIsNone(_to_float(float("nan")))

    def test_negative_passes_through(self):
        self.assertAlmostEqual(_to_float(-3.0), -3.0)

    def test_returns_float(self):
        result = _to_float(1)
        self.assertIsInstance(result, float)


class TestListToScores(unittest.TestCase):
    """Tests for channel_scoring._list_to_scores() — list-of-dicts to mapping."""

    def test_valid_items_extracted(self):
        items = [{"channel": "alpha", "weight": 1.5}, {"channel": "beta", "weight": 0.5}]
        result = _list_to_scores(items)
        self.assertAlmostEqual(result["alpha"], 1.5)
        self.assertAlmostEqual(result["beta"], 0.5)

    def test_non_dict_items_skipped(self):
        items = ["string", 42, {"channel": "gamma", "weight": 2.0}]
        result = _list_to_scores(items)
        self.assertEqual(list(result.keys()), ["gamma"])

    def test_non_string_channel_skipped(self):
        items = [{"channel": 123, "weight": 1.0}]
        result = _list_to_scores(items)
        self.assertEqual(result, {})

    def test_non_numeric_weight_skipped(self):
        items = [{"channel": "alpha", "weight": "not_a_float"}]
        result = _list_to_scores(items)
        self.assertEqual(result, {})

    def test_returns_dict(self):
        self.assertIsInstance(_list_to_scores([]), dict)


class TestValidateScoresExtended(unittest.TestCase):
    """Extended tests for validate_scores()."""

    def test_non_string_keys_skipped(self):
        scores = {123: 1.0, "alpha": 0.5}
        result = validate_scores(scores)
        self.assertNotIn(123, result)
        self.assertIn("alpha", result)

    def test_non_numeric_values_skipped(self):
        scores = {"alpha": "bad", "beta": 0.5}
        result = validate_scores(scores)
        self.assertNotIn("alpha", result)
        self.assertIn("beta", result)

    def test_normalize_sums_to_one(self):
        scores = {"a": 1.0, "b": 3.0}
        result = validate_scores(scores, normalize=True)
        self.assertAlmostEqual(sum(result.values()), 1.0, places=5)

    def test_non_dict_returns_empty(self):
        self.assertEqual(validate_scores([1, 2, 3]), {})

    def test_empty_dict_returns_empty(self):
        self.assertEqual(validate_scores({}), {})


class TestLoadChannelScoresListFormat(unittest.TestCase):
    """Tests for load_channel_scores() with list-format JSON."""

    def test_list_format_loads(self):
        import json, tempfile, os
        data = [{"channel": "alpha", "weight": 1.5}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_channel_scores(path)
            self.assertIn("alpha", result)
        finally:
            os.unlink(path)

    def test_default_scores_is_dict(self):
        self.assertIsInstance(DEFAULT_SCORES, dict)
        self.assertGreater(len(DEFAULT_SCORES), 0)


if __name__ == "__main__":
    unittest.main()
