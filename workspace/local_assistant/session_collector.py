#!/usr/bin/env python3
"""
Session Learning Collector
Pulls recent session interactions and saves to learning pipeline
Run via cron: every 30 minutes
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path("/home/jeebs/src/clawd")
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from local_assistant.learning_pipeline import save_sample, DATA_DIR

def collect_recent_interactions(hours: int = 1):
    """Pull recent interactions from session logs"""
    # This would pull from OpenClaw session storage
    # For now, creates a marker file for manual review
    
    marker = DATA_DIR / f"session_collect_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.marker"
    marker.write_text(f"Collected at {datetime.now(timezone.utc).isoformat()}\n")
    print(f"Session marker created: {marker.name}")
    
    # TODO: Integrate with OpenClaw session storage
    # session_store = REPO_ROOT / ".openclaw/sessions"
    # for session_file in session_store.glob("*.json"):
    #     parse and save samples
    
    return marker

if __name__ == "__main__":
    print(f"[{datetime.now().isoformat()}] Session collector ran")
    collect_recent_interactions()
