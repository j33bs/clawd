import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from narrative_distill import distill_episodes  # noqa: E402


class TestNarrativeDistill(unittest.TestCase):
    def test_distillation_is_stable_for_fixed_fixture(self):
        episodes = [
            {"id": "e1", "text": "Router selected local provider for coding task"},
            {"id": "e2", "text": "Router selected local provider for coding tasks"},
            {"id": "e3", "text": "Witness ledger committed routing decision hash"},
        ]
        out = distill_episodes(episodes, max_items=10)
        self.assertGreaterEqual(len(out), 2)
        self.assertEqual(out[0]["support_count"], 2)
        self.assertEqual(out[0]["source_ids"], ["e1", "e2"])
        self.assertIn("router", out[0]["topics"])

    def test_max_items_is_respected(self):
        episodes = [{"id": f"e{i}", "text": f"Episode {i} distinct token {i}"} for i in range(80)]
        out = distill_episodes(episodes, max_items=5)
        self.assertEqual(len(out), 5)


if __name__ == "__main__":
    unittest.main()
