#!/usr/bin/env python3
"""
Research Wanderer - A research agent that keeps exploring between sessions.
Drift-friendly: runs in background, accumulates findings, surfaces new questions.

Usage:
  python3 research_wanderer.py add "topic to research"
  python3 research_wanderer.py wander    # Do research on queued topics
  python3 research_wanderer.py queue      # Show pending topics
  python3 research_wanderer.py status      # Show recent findings
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QUEUE_FILE = SCRIPT_DIR / "queue.json"
FINDINGS_FILE = SCRIPT_DIR / "findings.json"
LOG_FILE = SCRIPT_DIR / "wander_log.md"

DEFAULT_TOPICS = [
    "predictive processing vs next token prediction",
    "AI consciousness measurement integrated information",
    "multi-agent collective cognition emergence",
    "LLM world models internal representations",
    "embodied cognition symbol grounding AI",
    "AI memory consolidation sleep replay",
    "distributed AI identity continuity",
    "alien intelligence detection framework",
]

def load_queue():
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return {"topics": DEFAULT_TOPICS, "completed": [], "last_wander": None}

def save_queue(q):
    with open(QUEUE_FILE, "w") as f:
        json.dump(q, f, indent=2)

def load_findings():
    if FINDINGS_FILE.exists():
        with open(FINDINGS_FILE) as f:
            return json.load(f)
    return {"findings": [], "questions_generated": []}

def save_findings(findings):
    with open(FINDINGS_FILE, "w") as f:
        json.dump(findings, f, indent=2)

def add_topic(topic):
    q = load_queue()
    if topic not in q["topics"] and topic not in q["completed"]:
        q["topics"].append(topic)
        save_queue(q)
        print(f"✅ Added: {topic}")
    else:
        print(f"📝 Already in queue: {topic}")

def show_queue():
    q = load_queue()
    print("\n📚 Research Queue:")
    for i, t in enumerate(q["topics"], 1):
        print(f"  {i}. {t}")
    if q["completed"]:
        print(f"\n✅ Completed ({len(q['completed'])}):")
        for t in q["completed"][-5:]:
            print(f"  • {t}")

def show_status():
    f = load_findings()
    q = load_queue()
    print(f"\n🧠 Research Wanderer Status")
    print(f"   Topics in queue: {len(q['topics'])}")
    print(f"   Topics completed: {len(q['completed'])}")
    print(f"   Findings recorded: {len(f['findings'])}")
    print(f"   Questions generated: {len(f['questions_generated'])}")
    if q["last_wander"]:
        print(f"   Last wander: {q['last_wander']}")
    
    if f["findings"]:
        print(f"\n📡 Recent findings:")
        for finding in f["findings"][-3:]:
            print(f"  - {finding[:100]}...")

def log_wander(content):
    with open(LOG_FILE, "a") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n\n---\n\n")

def main():
    if len(sys.argv) < 2:
        show_status()
        return
    
    cmd = sys.argv[1]
    
    if cmd == "add":
        if len(sys.argv) < 3:
            print("Usage: research_wanderer.py add 'topic'")
            sys.exit(1)
        add_topic(sys.argv[2])
    
    elif cmd == "queue":
        show_queue()
    
    elif cmd == "status":
        show_status()
    
    elif cmd == "wander":
        q = load_queue()
        if not q["topics"]:
            print("No topics to research. Add some!")
            sys.exit(1)
        
        topic = q["topics"][0]
        print(f"Wandering: {topic}")
        
        # Mark as explored (in real impl, would do actual research here)
        q["topics"].pop(0)
        q["completed"].append(topic)
        q["last_wander"] = datetime.now().isoformat()
        
        # Generate a placeholder finding (would be web search in full impl)
        finding = f"Explored: {topic}"
        
        f = load_findings()
        f["findings"].append({
            "topic": topic,
            "finding": finding,
            "timestamp": datetime.now().isoformat()
        })
        
        # Generate new question
        new_q = f"What would {topic} mean for TACTI(C)-R?"
        f["questions_generated"].append({
            "question": new_q,
            "from_topic": topic,
            "timestamp": datetime.now().isoformat()
        })
        
        save_queue(q)
        save_findings(f)
        
        log_wander(f"Wandered: {topic}\n\nGenerated question: {new_q}")
        
        print(f"✅ Wandered: {topic}")
        print(f"   New question: {new_q}")
    
    elif cmd == "init":
        q = load_queue()
        if not q["topics"]:
            q["topics"] = DEFAULT_TOPICS
            save_queue(q)
            print("✅ Initialized with default topics")
        else:
            print("Queue already initialized")
    
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: add, queue, status, wander, init")

if __name__ == "__main__":
    main()
