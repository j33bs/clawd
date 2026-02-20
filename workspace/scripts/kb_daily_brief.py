#!/usr/bin/env python3
"""
KB Daily Brief - Pull a random research highlight for the morning briefing
"""
import json
import random
from pathlib import Path

KB_GRAPH = Path(__file__).parent.parent / "knowledge_base" / "data" / "graph.jsonl"

def get_research_highlight():
    """Get a random research entry from the KB."""
    entries = []
    with open(KB_GRAPH) as f:
        for line in f:
            e = json.loads(line)
            if e.get('entity_type', '').startswith('research:'):
                entries.append(e)
    
    if not entries:
        return None
    
    entry = random.choice(entries)
    topic = entry.get('entity_type', '').replace('research:', '')
    
    # Extract key points from content
    content = entry.get('content', '')[:500]
    lines = content.split('\n')
    key_points = [l for l in lines if l.strip() and not l.startswith('#')][:3]
    
    return {
        'title': entry.get('name', 'Untitled')[:70],
        'topic': topic,
        'key_points': key_points,
        'url': entry.get('metadata', {}).get('url')
    }

def format_for_brief():
    """Format the highlight for the daily brief."""
    highlight = get_research_highlight()
    if not highlight:
        return ""
    
    lines = [
        "",
        "### 🔬 Daily Research Highlight",
        f"**Topic:** {highlight['topic'].upper()}",
        "",
        f"**{highlight['title']}**",
        ""
    ]
    
    for point in highlight['key_points']:
        lines.append(f"- {point}")
    
    if highlight.get('url'):
        lines.append(f"\n[Read more]({highlight['url']})")
    
    return '\n'.join(lines)

if __name__ == "__main__":
    print(format_for_brief())
