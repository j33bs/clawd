import math
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.reservoir import Reservoir  # noqa: E402


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


class TestReservoir(unittest.TestCase):
    def test_deterministic_step_with_seed(self):
        r1 = Reservoir.init(dim=20, leak=0.4, spectral_scale=0.9, seed=42)
        r2 = Reservoir.init(dim=20, leak=0.4, spectral_scale=0.9, seed=42)
        s1 = r1.step({"intent": "audit"}, {"agent": "main"}, {"deg": 3})
        s2 = r2.step({"intent": "audit"}, {"agent": "main"}, {"deg": 3})
        self.assertEqual([round(x, 8) for x in s1], [round(x, 8) for x in s2])

    def test_state_decays_with_no_input(self):
        r = Reservoir.init(dim=16, leak=0.35, spectral_scale=0.8, seed=9)
        first = r.step({"x": 2.0}, {"y": 1.0}, {"z": 1.0})
        baseline = sum(abs(v) for v in first)
        for _ in range(15):
            r.step({}, {}, {})
        decayed = sum(abs(v) for v in r.step({}, {}, {}))
        self.assertLess(decayed, baseline)

    def test_similar_inputs_yield_correlated_states(self):
        r = Reservoir.init(dim=18, leak=0.3, spectral_scale=0.7, seed=5)
        s1 = r.step({"intent": "memory query"}, {"agent": "main"}, {"peers": ["a", "b"]})
        r.reset("s2")
        s2 = r.step({"intent": "memory lookup"}, {"agent": "main"}, {"peers": ["a", "b"]})
        self.assertGreater(_cos(s1, s2), 0.55)


if __name__ == "__main__":
    unittest.main()

