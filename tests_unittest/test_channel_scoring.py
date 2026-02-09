import json
import os
import tempfile
import unittest

from core_infra.channel_scoring import DEFAULT_SCORES, load_channel_scores, validate_scores


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


if __name__ == "__main__":
    unittest.main()
