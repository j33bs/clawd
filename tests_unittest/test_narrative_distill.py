import unittest
from pathlib import Path
import os
import json
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from narrative_distill import distill_episodes, write_semantic_entries  # noqa: E402


class TestNarrativeDistill(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_distillation_is_stable_for_fixed_fixture(self):
        episodes = [
            {"id": "e1", "text": "Router selected local provider for coding task", "timestamp_utc": "2026-02-20T00:00:00Z"},
            {"id": "e2", "text": "Router selected local provider for coding tasks", "timestamp_utc": "2026-02-20T00:00:01Z"},
            {"id": "e3", "text": "Witness ledger committed routing decision hash", "timestamp_utc": "2026-02-20T00:00:02Z"},
        ]
        out = distill_episodes(episodes, max_items=10)
        self.assertGreaterEqual(len(out), 2)
        self.assertEqual(out[0]["support_count"], 2)
        self.assertEqual(out[0]["source_ids"], ["e1", "e2"])
        self.assertIn("router", out[0]["topics"])
        self.assertEqual(out[0]["timestamp_utc"], "2026-02-20T00:00:00Z")

    def test_max_items_is_respected(self):
        episodes = [{"id": f"e{i}", "text": f"Episode {i} distinct token {i}"} for i in range(80)]
        out = distill_episodes(episodes, max_items=5)
        self.assertEqual(len(out), 5)

    def test_semantic_store_write_is_idempotent_when_flag_on(self):
        os.environ["OPENCLAW_NARRATIVE_DISTILL"] = "1"
        entries = [
            {
                "fact": "Router selected local provider for coding task",
                "entities": [],
                "topics": ["router"],
                "support_count": 2,
                "source_ids": ["e1", "e2"],
                "timestamp_utc": "2026-02-20T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "workspace" / "hivemind" / "data").mkdir(parents=True, exist_ok=True)
            first = write_semantic_entries(entries, repo_root=root)
            second = write_semantic_entries(entries, repo_root=root)
            trails = root / "workspace" / "hivemind" / "data" / "trails.jsonl"
            rows = [json.loads(line) for line in trails.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(first["added"], 1)
        self.assertEqual(second["added"], 0)
        self.assertEqual(len(rows), 1)

    def test_flag_off_produces_no_write(self):
        os.environ["OPENCLAW_NARRATIVE_DISTILL"] = "0"
        entries = [
            {
                "fact": "Router selected local provider for coding task",
                "entities": [],
                "topics": ["router"],
                "support_count": 2,
                "source_ids": ["e1", "e2"],
                "timestamp_utc": "2026-02-20T00:00:00Z",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = write_semantic_entries(entries, repo_root=root)
            trails = root / "workspace" / "hivemind" / "data" / "trails.jsonl"
        self.assertEqual(result["backend"], "disabled")
        self.assertEqual(result["added"], 0)
        self.assertFalse(trails.exists())


if __name__ == "__main__":
    unittest.main()
