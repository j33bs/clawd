#!/usr/bin/env python3
"""
Explicit Epistemic States - Track confidence in knowledge
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_FILE = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "graph.jsonl"

def get_knowledge_with_confidence(query: str = None):
    """Get knowledge entries with confidence levels."""
    results = []
    
    with open(KB_FILE) as f:
        for line in f:
            entry = json.loads(line)
            confidence = entry.get("metadata", {}).get("confidence", 0.5)
            results.append({
                "name": entry.get("name"),
                "content": entry.get("content", "")[:200],
                "confidence": confidence,
                "topic": entry.get("entity_type", "unknown")
            })
    
    if query:
        # Simple keyword matching
        results = [r for r in results if query.lower() in r["content"].lower() or 
                   query.lower() in r["name"].lower()]
    
    return results

def add_with_confidence(name: str, content: str, topic: str, confidence: float = 0.5):
    """Add entry with explicit confidence."""
    entry = {
        "id": f"epistemic_{name[:20].replace(' ', '_')}_{len(content)}",
        "name": name,
        "entity_type": f"epistemic:{topic}",
        "content": content,
        "source": "epistemic",
        "metadata": {
            "topic": topic,
            "confidence": confidence,
            "confidence_label": confidence_to_label(confidence)
        }
    }
    
    with open(KB_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return entry

def confidence_to_label(c: float) -> str:
    if c >= 0.9: return "certain"
    if c >= 0.7: return "confident"
    if c >= 0.5: return "likely"
    if c >= 0.3: return "uncertain"
    return "speculative"

def i_know_statement(query: str = None) -> str:
    """Generate 'I know X with Y% confidence' statement."""
    entries = get_knowledge_with_confidence(query)
    
    if not entries:
        return f"I don't have knowledge about '{query}'"
    
    statements = []
    for e in entries[:3]:
        c_pct = int(e["confidence"] * 100)
        statements.append(f"- {e['name']}: {c_pct}% confident")
    
    return "My knowledge:\n" + "\n".join(statements)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(i_know_statement(" ".join(sys.argv[1:])))
    else:
        # Show some knowledge
        print(i_know_statement())
