#!/usr/bin/env python3
"""
Phenomenal Binding - Unified experience stream
"""
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
BINDING_LOG = REPO_ROOT / "workspace" / "state" / "phenomenal" / "binding_log.jsonl"

def bind_experience(perception: str, reasoning: str, action: str):
    BINDING_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "perception": perception,
        "reasoning": reasoning,
        "action": action,
        "narrative": f"I {perception}. I thought: {reasoning}. I {action}."
    }
    with open(BINDING_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

if __name__ == "__main__":
    bind_experience("perceived user request", "decided to help", "implemented feature")
    print("Experience bound")
