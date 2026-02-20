#!/usr/bin/env python3
"""Failure Archaeology - Deep failure analysis"""
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
FAILURES_DIR = REPO_ROOT / "workspace" / "failures"

def log_failure(error: str, context: str = ""):
    failure_id = f"failure_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    entry = {
        "id": failure_id,
        "error": error,
        "context": context,
        "root_cause": "TBD",
        "lesson": "TBD",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    with open(FAILURES_DIR / f"{failure_id}.json", "w") as f:
        json.dump(entry, f, indent=2)
    return entry

if __name__ == "__main__":
    log_failure("missing_api_key", "TeamChat planning")
    print("Failure logged")
