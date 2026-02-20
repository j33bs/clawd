#!/usr/bin/env python3
"""
Dream Consolidation - Nightly replay and analysis of day's events
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parents[2]

def analyze_day():
    """Analyze previous day's events."""
    events_file = REPO_ROOT / "workspace" / "state" / "tacti_cr" / "events.jsonl"
    if not events_file.exists():
        return {"error": "No events file"}
    
    # Load last 24 hours of events
    events = []
    with open(events_file) as f:
        for line in f:
            try:
                e = json.loads(line)
                events.append(e)
            except:
                pass
    
    # Analyze patterns
    event_types = Counter(e.get("event", e.get("type", "unknown")) for e in events)
    success_count = sum(1 for e in events if "success" in str(e))
    failure_count = sum(1 for e in events if "fail" in str(e))
    
    return {
        "total_events": len(events),
        "event_types": dict(event_types),
        "successes": success_count,
        "failures": failure_count,
        "patterns": "Analyze for patterns"
    }

def dream_consolidation():
    """Run nightly consolidation."""
    analysis = analyze_day()
    
    # Save to dream log
    dream_file = REPO_ROOT / "workspace" / "state" / "dreams" / f"{datetime.now(timezone.utc).date()}.json"
    dream_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(dream_file, "w") as f:
        json.dump(analysis, f, indent=2)
    
    print(f"Dream consolidation: {analysis['total_events']} events analyzed")
    return analysis

if __name__ == "__main__":
    dream_consolidation()
