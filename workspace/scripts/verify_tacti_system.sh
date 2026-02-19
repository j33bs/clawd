#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

echo "[verify] running TACTI(C)-R deterministic unit tests"
python3 -m unittest \
  tests_unittest/test_hivemind_peer_graph.py \
  tests_unittest/test_hivemind_reservoir.py \
  tests_unittest/test_hivemind_physarum_router.py \
  tests_unittest/test_hivemind_trails.py \
  tests_unittest/test_hivemind_dynamics_pipeline.py \
  tests_unittest/test_hivemind_active_inference.py \
  tests_unittest/test_policy_router_active_inference_hook.py

echo "[verify] generating offline dynamics snapshot"
export ENABLE_MURMURATION=1
export ENABLE_RESERVOIR=1
export ENABLE_PHYSARUM_ROUTER=1
export ENABLE_TRAIL_MEMORY=1
python3 - <<'PY'
import json
from pathlib import Path
import sys

repo = Path.cwd()
sys.path.insert(0, str(repo / "workspace" / "hivemind"))
from hivemind.dynamics_pipeline import TactiDynamicsPipeline  # noqa: E402
from hivemind.trails import TrailStore  # noqa: E402

artifact_dir = repo / "workspace" / "artifacts" / "tacti_system"
artifact_dir.mkdir(parents=True, exist_ok=True)
trail_path = artifact_dir / "verify_trails.jsonl"
pipeline = TactiDynamicsPipeline(
    agent_ids=["main", "claude-code", "codex"],
    seed=21,
    trail_store=TrailStore(path=trail_path),
)
plan = pipeline.plan_consult_order(
    source_agent="main",
    target_intent="verification",
    context_text="verify murmuration reservoir physarum trails",
    candidate_agents=["claude-code", "codex"],
)
pipeline.observe_outcome(
    source_agent="main",
    path=plan["paths"][0],
    success=True,
    latency=25,
    tokens=160,
    reward=1.0,
    context_text="verification",
)
report = {
    "consult_order": plan["consult_order"],
    "paths": plan["paths"],
    "scores": plan["scores"],
    "snapshot": pipeline.snapshot(),
}
(artifact_dir / "verify_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "artifact": str(artifact_dir / "verify_report.json")}))
PY

echo "[verify] complete"

