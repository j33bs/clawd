from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
HIVEMIND_ROOT = WORKSPACE_ROOT / "hivemind"

import sys
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from tacti_cr.arousal_oscillator import ArousalOscillator
from tacti_cr.dream_consolidation import run_consolidation
from tacti_cr.expression import compute_expression
from tacti_cr.mirror import behavioral_fingerprint, update_from_event
from tacti_cr.prefetch import PrefetchCache, predict_topics
from tacti_cr.semantic_immune import assess_content, approve_quarantine
from tacti_cr.temporal_watchdog import detect_temporal_drift, temporal_reset_event, update_beacon
from tacti_cr.valence import current_valence, routing_bias, update_valence
from hivemind.stigmergy import StigmergyMap
SOURCE_UI_ROOT = WORKSPACE_ROOT / "source-ui"
if str(SOURCE_UI_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_UI_ROOT))
from api.trails import trails_heatmap_payload


class TestTactiCrNovel10(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ.setdefault("TACTI_CR_ENABLE", "1")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_arousal_oscillator_bins_and_explain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "workspace" / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "2026-02-19.md").write_text(
                "[09:12] alpha\n2026-02-19T15:33:00Z beta\n15:40 gamma\n",
                encoding="utf-8",
            )
            os.environ["TACTI_CR_AROUSAL_OSC"] = "1"
            osc = ArousalOscillator(repo_root=root)
            exp = osc.explain(datetime(2026, 2, 19, 9, 0, tzinfo=timezone.utc))
            self.assertIn("multiplier", exp)
            self.assertGreaterEqual(exp["multiplier"], 0.0)
            self.assertLessEqual(exp["multiplier"], 1.0)
            self.assertGreater(exp["bins_used"], 0)

    def test_expression_profile_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy = root / "workspace" / "policy"
            policy.mkdir(parents=True)
            (policy / "expression_manifest.json").write_text(
                json.dumps({"features": [{"feature_name": "prefetch", "activation_conditions": {"valence_min": -0.1}, "suppression_conditions": {}, "priority": 1}]}, indent=2),
                encoding="utf-8",
            )
            os.environ["TACTI_CR_EXPRESSION_ROUTER"] = "1"
            profile = compute_expression(
                datetime(2026, 2, 19, 10, 0, tzinfo=timezone.utc),
                {"valence": 0.2, "budget_remaining": 0.9, "local_available": True},
                manifest_path=policy / "expression_manifest.json",
            )
            self.assertIn("enabled_features", profile)
            self.assertIn("prefetch", profile["enabled_features"])

    def test_temporal_watchdog_detection(self):
        os.environ["TACTI_CR_TEMPORAL_WATCHDOG"] = "1"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stale = datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc)
            update_beacon(root, now=stale)
            now = datetime(2026, 2, 19, 2, 0, tzinfo=timezone.utc)
            findings = detect_temporal_drift("done at 2026-02-19T03:30:00Z", now=now, beacon={"updated_at": stale.isoformat().replace("+00:00", "Z")})
            kinds = {f["type"] for f in findings}
            self.assertIn("stale_context_treated_fresh", kinds)
            self.assertIn("future_event_marked_done", kinds)
            ev = temporal_reset_event("done at 2026-02-19T03:30:00Z", now=now, repo_root=root)
            self.assertIsNotNone(ev)
            self.assertEqual(ev["event"], "temporal_reset")

    def test_dream_consolidation_stable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "workspace" / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "2026-02-19.md").write_text(
                "[09:10] Validated deterministic routing gate behavior.\n"
                "[10:20] Fixed flaky parser in watchdog module.\n"
                "[15:00] Added concise audit runbook for reviewers.\n",
                encoding="utf-8",
            )
            os.environ["TACTI_CR_DREAM_CONSOLIDATION"] = "1"
            res = run_consolidation(root, day="2026-02-19", now=datetime(2026, 2, 19, 16, 0, tzinfo=timezone.utc))
            self.assertTrue(res["ok"], res)
            report = Path(res["report_path"]).read_text(encoding="utf-8")
            self.assertIn("# Dream Report 2026-02-19", report)
            self.assertIn("## Emergent Insights", report)
            self.assertGreaterEqual(report.count("- "), 5)

    def test_semantic_immune_quarantine_and_approve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.environ["TACTI_CR_SEMANTIC_IMMUNE"] = "1"
            for i in range(8):
                assess_content(root, f"normal stable content token {i}")
            out = assess_content(root, "ZXQVPLM unusual synthetic anomaly signature")
            self.assertTrue(out["quarantined"], out)
            approved = approve_quarantine(root, out["content_hash"])
            self.assertTrue(approved["ok"], approved)

    def test_stigmergy_decay_ordering(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "map.json"
            sm = StigmergyMap(path=path)
            now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
            sm.deposit_mark("routing", 1.0, 0.01, "planner", now=now)
            sm.deposit_mark("memory", 0.9, 0.2, "coder", now=now)
            ranked = sm.query_marks(now=now + timedelta(hours=10), top_n=2)
            self.assertEqual(ranked[0]["topic"], "routing")
            avoid = sm.suggest_avoid_topics(now=now, threshold=0.5)
            self.assertIn("routing", avoid)

    def test_mirror_and_valence_local_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.environ["TACTI_CR_MIRROR"] = "1"
            os.environ["TACTI_CR_VALENCE"] = "1"
            update_from_event("coder", {"event": "planner_review", "data": {"decision": "revise"}}, repo_root=root)
            fp = behavioral_fingerprint("coder", repo_root=root)
            self.assertGreater(fp["metrics"]["escalation_rate"], 0.0)
            update_valence("coder", {"failed": True, "retry_loops": 2}, repo_root=root)
            val = current_valence("coder", repo_root=root)
            self.assertLess(val, 0.0)
            bias = routing_bias("coder", repo_root=root)
            self.assertIn("prefer_local", bias)

    def test_prefetch_cache_and_predict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            os.environ["TACTI_CR_PREFETCH"] = "1"
            topics = predict_topics("routing routing memory watchdog routing trails")
            self.assertEqual(topics[0], "routing")
            cache = PrefetchCache(repo_root=root)
            cache.record_prefetch("routing", ["doc:a"])
            for _ in range(100):
                cache.record_hit(False)
            self.assertEqual(cache.depth(), 2)

    def test_source_ui_trails_payload_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "workspace" / "state" / "stigmergy"
            path.mkdir(parents=True, exist_ok=True)
            (path / "map.json").write_text(json.dumps([
                {"topic": "routing", "intensity": 1.0, "decay_rate": 0.1, "deposited_by": "planner", "timestamp": "2026-02-19T10:00:00Z"},
                {"topic": "memory", "intensity": 0.5, "decay_rate": 0.1, "deposited_by": "coder", "timestamp": "2026-02-19T10:00:00Z"},
            ]), encoding="utf-8")
            payload = trails_heatmap_payload(root, top_n=2)
            self.assertEqual(payload["count"], 2)
            self.assertEqual(payload["items"][0]["topic"], "routing")


if __name__ == "__main__":
    unittest.main()
