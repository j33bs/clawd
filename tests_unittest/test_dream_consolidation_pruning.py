import copy
import os
import unittest

from workspace.tacti_cr.dream_consolidation import prune_competing_clusters


class TestDreamConsolidationPruning(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["TACTI_CR_ENABLE"] = "1"
        os.environ["TACTI_CR_DREAM_CONSOLIDATION"] = "1"
        os.environ["OPENCLAW_DREAM_PRUNING"] = "0"
        os.environ["OPENCLAW_DREAM_PRUNE"] = "0"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def _fixture(self):
        return [
            {
                "cluster_id": "strong",
                "text": "routing failure in policy router",
                "mass": 2.0,
                "reinforcement_count": 5,
                "tags": ["routing", "policy"],
                "exemplars": ["routing failure in policy router"],
                "updated_at": "2026-02-20T00:00:00Z",
            },
            {
                "cluster_id": "weak",
                "text": "policy router routing failure",
                "mass": 1.2,
                "reinforcement_count": 1,
                "tags": ["incident"],
                "exemplars": ["policy router routing failure"],
                "updated_at": "2026-02-20T00:00:00Z",
            },
        ]

    def test_pruning_is_flag_gated(self):
        rows = self._fixture()
        out = prune_competing_clusters(copy.deepcopy(rows), sim_threshold=0.8, max_merge_per_pass=1)
        self.assertEqual(out, rows)

        os.environ["OPENCLAW_DREAM_PRUNING"] = "1"
        pruned = prune_competing_clusters(copy.deepcopy(rows), sim_threshold=0.8, max_merge_per_pass=1)
        self.assertNotEqual(pruned, rows)

    def test_pruning_absorbs_and_decays_weaker_cluster(self):
        os.environ["OPENCLAW_DREAM_PRUNING"] = "1"
        rows = self._fixture()
        pruned = prune_competing_clusters(copy.deepcopy(rows), sim_threshold=0.8, max_merge_per_pass=1)

        strong = next(item for item in pruned if item.get("cluster_id") == "strong")
        self.assertIn("weak", strong.get("absorbed", []))
        self.assertIn("incident", strong.get("tags", []))
        self.assertIn("policy router routing failure", strong.get("exemplars", []))

        weak = next(item for item in pruned if item.get("cluster_id") == "weak")
        self.assertLess(float(weak["mass"]), 1.2 * 0.5)  # decayed faster than baseline 0.5
        self.assertTrue(bool(weak.get("decayed_by_pruning")))

    def test_pruning_is_deterministic(self):
        os.environ["OPENCLAW_DREAM_PRUNING"] = "1"
        rows = self._fixture()
        first = prune_competing_clusters(copy.deepcopy(rows), sim_threshold=0.8, max_merge_per_pass=1)
        second = prune_competing_clusters(copy.deepcopy(rows), sim_threshold=0.8, max_merge_per_pass=1)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
