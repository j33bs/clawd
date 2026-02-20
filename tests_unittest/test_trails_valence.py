import os
import tempfile
import unittest
from pathlib import Path

from workspace.hivemind.hivemind.trails import TrailStore


class TestTrailsValence(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_follow_returns_dampened_valence_when_flag_on(self):
        os.environ["OPENCLAW_TRAILS_VALENCE"] = "1"
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl")
            store.deposit({"text": "route local", "tags": ["routing"]}, valence=0.8)
            _trail, inherited = store.follow("route local")
        self.assertEqual(inherited, 0.4)

    def test_flag_off_ignores_valence_fields(self):
        os.environ["OPENCLAW_TRAILS_VALENCE"] = "0"
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl")
            store.deposit({"text": "route local", "tags": ["routing"]}, valence=0.8)
            rows = store._read_all()
            _trail, inherited = store.follow("route local")
        self.assertNotIn("valence_signature", rows[0])
        self.assertIsNone(inherited)

    def test_consensus_aggregation_is_deterministic(self):
        os.environ["OPENCLAW_TRAILS_VALENCE"] = "1"
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl")
            store.deposit({"text": "route local", "tags": ["routing"]}, valence=1.0)
            store.deposit({"text": "route local", "tags": ["routing"]}, valence=0.0)
            store.deposit({"text": "route local", "tags": ["routing"]}, valence=1.0)
            rows = store._read_all()
        self.assertEqual(rows[1]["valence_consensus"], 0.5)
        self.assertEqual(rows[2]["valence_consensus"], 0.75)


if __name__ == "__main__":
    unittest.main()
