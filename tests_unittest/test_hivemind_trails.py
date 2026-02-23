import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.trails import TrailStore  # noqa: E402


class TestTrailStore(unittest.TestCase):
    def test_decay_reduces_effective_strength(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trails.jsonl"
            store = TrailStore(path=path, half_life_hours=1.0)
            trail_id = store.add({"text": "route cache miss", "tags": ["routing"], "strength": 2.0, "meta": {}})
            now = datetime.now(timezone.utc)
            initial = store.query("route cache", k=1, now=now)[0]
            store.decay(now=now + timedelta(hours=2))
            later = store.query("route cache", k=1, now=now + timedelta(hours=2))[0]
            self.assertEqual(initial["trail_id"], trail_id)
            self.assertLess(later["effective_strength"], initial["effective_strength"])

    def test_reinforcement_increases_rank(self):
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl", half_life_hours=12.0)
            t1 = store.add({"text": "python memory tool", "tags": ["memory"], "strength": 1.0, "meta": {}})
            t2 = store.add({"text": "python memory tool stable", "tags": ["memory"], "strength": 1.0, "meta": {}})
            before = [x["trail_id"] for x in store.query("python memory", k=2)]
            store.reinforce(t2, 1.5)
            after = [x["trail_id"] for x in store.query("python memory", k=2)]
            self.assertIn(t1, before)
            self.assertEqual(after[0], t2)

    def test_writer_persists_source_field(self):
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl")
            trail_id = store.add(
                {
                    "text": "wander curiosity pass",
                    "tags": ["wander"],
                    "strength": 1.1,
                    "source": "wander",
                    "meta": {},
                }
            )
            hit = store.query("wander curiosity", k=1)[0]
            self.assertEqual(hit["trail_id"], trail_id)
            self.assertEqual(hit["source"], "wander")

    def test_reader_defaults_missing_source_to_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trails.jsonl"
            path.write_text(
                '{"trail_id":"legacy-1","text":"legacy item","tags":["routing"],"embedding":[1,0,0],"strength":1.0,"meta":{},"created_at":"2026-02-23T00:00:00Z","updated_at":"2026-02-23T00:00:00Z"}\n',
                encoding="utf-8",
            )
            store = TrailStore(path=path)
            hit = store.query([1.0, 0.0, 0.0], k=1)[0]
            self.assertEqual(hit["source"], "unknown")


if __name__ == "__main__":
    unittest.main()
