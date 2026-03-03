#!/usr/bin/env python3
"""
Daily Brief Generator - Combines project status with KB research
"""
import json
import random
from pathlib import Path
from datetime import datetime

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
    content = entry.get('content', '')[:400]
    
    return {
        'title': entry.get('name', 'Untitled')[:70],
        'topic': topic,
        'content': content,
        'url': entry.get('metadata', {}).get('url')
    }

def generate_brief():
    highlight = get_research_highlight()
    date = datetime.now().strftime("%Y-%m-%d")
    
    brief = f"""# DAILY BRIEF - {date}

## Projects Status

### Directory Project (Affordable Counselling AU)
- Status: Month 1 - Research & Validation
- Primary niche: Free/low-cost/sliding-scale counselling directory
- Architecture: Modular, reusable skeleton
- See: workspace/directory-project/

### MISA Fundraising
- Weekly idea system: Active (Mondays @ 9am)
- Current idea: Week 1 - MISA Partner Directory
- See: workspace/misa-project/

### Quick Updates
- Telegram threading: Enabled (replyToMode: all)
- Gateway: Running
- vLLM: TACTI CR routing enabled (short requests → local, complex → cloud)

## 🔬 Today's Research Highlight
**Topic:** {highlight['topic'].upper()}

**{highlight['title']}**

{highlight['content'][:300]}...

{"[Read more](" + highlight['url'] + ")" if highlight.get('url') else ""}

## Today's Focus
Review project priorities, continue research, or move to next task.

## Links
- Directory: workspace/directory-project/
- MISA: workspace/misa-project/
- Memory: workspace/MEMORY.md
- Research KB: workspace/knowledge_base/
"""
    return brief

if __name__ == "__main__":
    print(generate_brief())
