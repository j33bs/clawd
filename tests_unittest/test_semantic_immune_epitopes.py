import os
import tempfile
import unittest
from pathlib import Path

import workspace.tacti_cr.semantic_immune as semantic_immune


class TestSemanticImmuneEpitopes(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        semantic_immune._EPITOPE_CACHE._rows.clear()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        semantic_immune._EPITOPE_CACHE._rows.clear()

    def test_resolved_contradiction_stores_epitope_and_flags_future_claim(self):
        os.environ["TACTI_CR_ENABLE"] = "1"
        os.environ["TACTI_CR_SEMANTIC_IMMUNE"] = "1"
        os.environ["OPENCLAW_SEMANTIC_IMMUNE_EPITOPES"] = "1"

        semantic_immune.cache_epitope("known losing belief about routing gate behavior")
        with tempfile.TemporaryDirectory() as td:
            result = semantic_immune.assess_content(Path(td), "known losing belief about routing gate behavior again")
        self.assertTrue(result["quarantined"])
        self.assertEqual(result["reason"], "epitope_cache_hit")

    def test_bounded_eviction_is_deterministic(self):
        os.environ["OPENCLAW_SEMANTIC_IMMUNE_EPITOPES"] = "1"
        for idx in range(6):
            semantic_immune.cache_epitope(f"claim {idx} unique", max_size=4)
        self.assertFalse(semantic_immune.epitope_cache_hit("claim 0 unique"))
        self.assertTrue(semantic_immune.epitope_cache_hit("claim 5 unique"))


if __name__ == "__main__":
    unittest.main()
