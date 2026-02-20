#!/usr/bin/env python3
"""
Metacognitive Loop - Log thoughts before acting
"""
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
METACOG_LOG = REPO_ROOT / "workspace" / "state" / "metacognition" / "thinking_log.jsonl"

def log_thinking(about: str, reason: str, plan: str = None):
    """Log what I'm about to do and why."""
    METACOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "about": about,
        "reason": reason,
        "plan": plan,
        "type": "thinking"
    }
    
    with open(METACOG_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return entry

def before_action(action: str, context: str = ""):
    """Convenience: log before taking an action."""
    return log_thinking(
        about=f"About to: {action}",
        reason=f"Context: {context}" if context else "User requested",
        plan=None
    )

def recent_thoughts(count: int = 5):
    """Get recent thoughts."""
    if not METACOG_LOG.exists():
        return []
    
    thoughts = []
    with open(METACOG_LOG) as f:
        lines = f.readlines()
        for line in lines[-count:]:
            thoughts.append(json.loads(line))
    
    return thoughts

def what_am_i_doing():
    """Return a summary of recent thinking."""
    thoughts = recent_thoughts(3)
    if not thoughts:
        return "I haven't been thinking much recently."
    
    summary = "I'm thinking about:\n"
    for t in thoughts:
        summary += f"- {t.get('about', 'unknown')}: {t.get('reason', '')}\n"
    return summary

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(before_action(sys.argv[1], " ".join(sys.argv[2:])))
    else:
        print(what_am_i_doing())
