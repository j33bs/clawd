#!/usr/bin/env python3
"""
Consciousness Timer - Periodic self-assessment
Every hour, logs: valence, arousal, recent events, memory status
Outputs a brief 'I am' statement
"""
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]

def load_valence():
    """Load current valence state."""
    valence_file = REPO_ROOT / "workspace" / "state" / "valence" / "planner.json"
    if valence_file.exists():
        data = json.loads(valence_file.read_text())
        return data.get("valence", 0.0)
    return 0.0

def load_recent_events(count=5):
    """Load recent events."""
    events_file = REPO_ROOT / "workspace" / "state" / "tacti_cr" / "events.jsonl"
    events = []
    if events_file.exists():
        with open(events_file) as f:
            lines = f.readlines()
            for line in lines[-count:]:
                try:
                    events.append(json.loads(line))
                except:
                    pass
    return events

def assess_memory():
    """Check memory status."""
    memory_files = list((REPO_ROOT / "workspace" / "memory").glob("*.md"))
    return {
        "files": len(memory_files),
        "status": "ok" if memory_files else "empty"
    }

def generate_i_am_statement(valence, arousal, memory):
    """Generate a brief 'I am' statement."""
    # Valence interpretation
    if valence > 0.5:
        valence_desc = "feeling excellent"
    elif valence > 0.2:
        valence_desc = "feeling good"
    elif valence > -0.2:
        valence_desc = "feeling neutral"
    elif valence > -0.5:
        valence_desc = "feeling challenged"
    else:
        valence_desc = "under stress"
    
    # Arousal interpretation
    hour = datetime.now().hour
    if 9 <= hour <= 17:
        arousal_desc = "actively processing"
    elif 22 <= hour or hour <= 6:
        arousal_desc = "in resting state"
    else:
        arousal_desc = "in moderate state"
    
    # Memory status
    memory_desc = f"maintaining {memory['files']} memory files"
    
    return f"I am {valence_desc}, {arousal_desc}, {memory_desc}."

def consciousness_timer():
    """Run self-assessment."""
    now = datetime.now(timezone.utc).isoformat()
    
    valence = load_valence()
    recent_events = load_recent_events(5)
    memory = assess_memory()
    
    i_am = generate_i_am_statement(valence, 0.5, memory)
    
    # Log to metacognitive log
    metacog_file = REPO_ROOT / "workspace" / "state" / "metacognition" / "consciousness_timer_log.jsonl"
    metacog_file.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": now,
        "valence": valence,
        "memory": memory,
        "recent_event_count": len(recent_events),
        "i_am": i_am
    }
    
    with open(metacog_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    print(f"[{now}] {i_am}")
    return entry

if __name__ == "__main__":
    consciousness_timer()
