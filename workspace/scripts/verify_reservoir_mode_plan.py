#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
if str(HIVEMIND_ROOT) not in sys.path:
    sys.path.insert(0, str(HIVEMIND_ROOT))

from hivemind.dynamics_pipeline import TactiDynamicsPipeline  # type: ignore  # noqa: E402
from hivemind.trails import TrailStore  # type: ignore  # noqa: E402


def main() -> int:
    env_patch = {
        "ENABLE_MURMURATION": "1",
        "ENABLE_RESERVOIR": "1",
        "ENABLE_PHYSARUM_ROUTER": "1",
        "ENABLE_TRAIL_MEMORY": "1",
    }
    old = {k: os.environ.get(k) for k in env_patch}
    os.environ.update(env_patch)
    try:
        with tempfile.TemporaryDirectory() as td:
            trails = TrailStore(path=Path(td) / "trails.jsonl")
            pipeline = TactiDynamicsPipeline(agent_ids=["main", "codex", "claude-code", "dali"], seed=17, trail_store=trails)
            base = {
                "source_agent": "main",
                "target_intent": "memory_query",
                "context_text": "design tradeoff synthesis",
                "candidate_agents": ["codex", "claude-code", "dali"],
            }
            focused = pipeline.plan_consult_order(**base, response_mode="focused")
            exploratory = pipeline.plan_consult_order(**base, response_mode="exploratory")
            payload = {
                "seed": 17,
                "focused": {
                    "consult_order": focused.get("consult_order", []),
                    "response_plan": focused.get("response_plan", {}),
                },
                "exploratory": {
                    "consult_order": exploratory.get("consult_order", []),
                    "response_plan": exploratory.get("response_plan", {}),
                },
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

