import unittest

from core_infra.strategy_blender import blend_signals


class TestStrategyBlender(unittest.TestCase):
    def test_empty(self):
        out = blend_signals([])
        self.assertEqual(out["signal"], 0.0)
        self.assertEqual(out["confidence"], 0.0)

    def test_weighted_average(self):
        items = [
            {"source": "a", "signal": 1.0, "weight": 2.0, "confidence": 1.0},
            {"source": "b", "signal": 0.0, "weight": 1.0, "confidence": 1.0},
        ]
        out = blend_signals(items)
        self.assertAlmostEqual(out["signal"], 2.0 / 3.0, places=6)
        self.assertGreater(out["confidence"], 0.0)

    def test_tie_break(self):
        items = [
            {"source": "a", "signal": 1.0, "weight": 1.0, "confidence": 1.0},
            {"source": "b", "signal": -1.0, "weight": 1.0, "confidence": 1.0},
        ]
        out = blend_signals(items, {"tie_break": "bull"})
        self.assertEqual(out["signal"], 1.0)


if __name__ == "__main__":
    unittest.main()
