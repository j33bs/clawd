from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
HIVEMIND_ROOT = WORKSPACE_ROOT / "hivemind"

import sys

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from tacti_cr.dream_consolidation import prune_competing_clusters
from tacti_cr.oscillatory_gating import OscillatoryGate
from tacti_cr.semantic_immune import assess_content, cache_epitope
from tacti_cr.temporal import TemporalMemory, text_embedding_proxy
from hivemind.active_inference import generate_counterfactual_routings
from hivemind.peer_graph import PeerGraph
from hivemind.trails import TrailStore


class TestEvolutionScaffolds(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_dream_prune_merges_competing_clusters(self):
        os.environ["TACTI_CR_ENABLE"] = "1"
        os.environ["TACTI_CR_DREAM_CONSOLIDATION"] = "1"
        os.environ["OPENCLAW_DREAM_PRUNE"] = "1"
        clusters = [
            {"cluster_id": "a", "text": "routing failure in policy router", "weight": 1.0},
            {"cluster_id": "b", "text": "routing failures in policy router", "weight": 0.6},
        ]
        pruned = prune_competing_clusters(clusters, sim_threshold=0.5, max_merge_per_pass=1)
        self.assertEqual(len(pruned), 1)
        self.assertGreater(pruned[0]["weight"], 1.0)

    def test_trail_valence_signature_is_dampened(self):
        os.environ["OPENCLAW_TRAIL_VALENCE"] = "1"
        with tempfile.TemporaryDirectory() as td:
            store = TrailStore(path=Path(td) / "trails.jsonl")
            store.add(
                {
                    "text": "route via local",
                    "tags": ["routing"],
                    "strength": 1.0,
                    "meta": {},
                    "valence_signature": [1.0, -0.5],
                    "valence_hops": 1,
                }
            )
            rows = store._read_all()  # deterministic fixture access
            self.assertEqual(rows[0]["valence_signature"], [0.5, -0.25])

    def test_surprise_gate_blocks_expected_and_keeps_novel(self):
        os.environ["OPENCLAW_SURPRISE_GATE"] = "1"
        mem = TemporalMemory(sync_hivemind=False)
        centroid = text_embedding_proxy("known stable routing event")

        blocked = mem.store(
            "known stable routing event",
            metadata={"reservoir_centroid": centroid, "surprise_threshold": 0.2},
        )
        self.assertEqual(mem.size, 0)
        self.assertEqual(blocked.metadata.get("surprise_blocked"), "1")

        written = mem.store(
            "zxqv anomaly witness contradiction",
            metadata={"reservoir_centroid": centroid, "surprise_threshold": 0.2},
        )
        self.assertEqual(mem.size, 1)
        self.assertNotEqual(written.metadata.get("surprise_blocked"), "1")

    def test_peer_annealing_reduces_churn_probability(self):
        os.environ["OPENCLAW_PEER_ANNEAL"] = "1"
        graph = PeerGraph.init(["a", "b", "c", "d", "e"], k=2, seed=3)
        high = graph.current_churn_probability()
        graph.tick(40.0)
        low = graph.current_churn_probability()
        self.assertGreater(high, low)

    def test_counterfactual_replay_is_stable(self):
        os.environ["OPENCLAW_COUNTERFACTUAL_REPLAY"] = "1"
        out = generate_counterfactual_routings(
            {"provider": "groq", "reason_code": "request_timeout"},
            candidates=["local_vllm_assistant", "groq", "ollama"],
            max_items=3,
        )
        self.assertEqual([row["provider"] for row in out], ["groq", "local_vllm_assistant", "ollama"])
        self.assertEqual(len(out), 3)

    def test_epitope_cache_flags_similar_claim(self):
        os.environ["TACTI_CR_ENABLE"] = "1"
        os.environ["TACTI_CR_SEMANTIC_IMMUNE"] = "1"
        os.environ["OPENCLAW_EPITOPE_CACHE"] = "1"
        cache_epitope("known losing belief about routing gate behavior")
        with tempfile.TemporaryDirectory() as td:
            out = assess_content(Path(td), "known losing belief about routing gate behavior with extras")
        self.assertTrue(out["quarantined"])
        self.assertEqual(out["reason"], "epitope_cache_hit")

    def test_oscillatory_gate_cycles_single_group(self):
        os.environ["OPENCLAW_OSCILLATORY_GATING"] = "1"
        gate = OscillatoryGate(phase=0)
        p0 = gate.tick()
        p1 = gate.tick()
        p2 = gate.tick()
        self.assertTrue(p0["enabled"])
        self.assertEqual(len(p0["active_groups"]), 1)
        self.assertNotEqual(p0["active_groups"], p1["active_groups"])
        self.assertNotEqual(p1["active_groups"], p2["active_groups"])


if __name__ == "__main__":
    unittest.main()
