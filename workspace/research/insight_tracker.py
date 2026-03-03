#!/usr/bin/env python3
"""
Insight Tracker
Tracks key insights and connections made during research.
"""
import json
from pathlib import Path
from datetime import datetime

class InsightTracker:
    def __init__(self, path="workspace/research/insights.json"):
        self.path = Path(path)
        self.insights = self._load()
    
    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                return json.load(f)
        return {"insights": [], "connections": [], "tags": {}}
    
    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self.insights, f, indent=2)
    
    def add_insight(self, text, category="general", tags=None):
        """Add a new insight."""
        insight = {
            "id": len(self.insights["insights"]) + 1,
            "text": text,
            "category": category,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat()
        }
        self.insights["insights"].append(insight)
        
        # Update tags
        for tag in insight["tags"]:
            if tag not in self.insights["tags"]:
                self.insights["tags"][tag] = []
            self.insights["tags"][tag].append(insight["id"])
        
        self._save()
        return insight
    
    def add_connection(self, from_id, to_id, relationship="relates_to"):
        """Connect two insights."""
        connection = {
            "from": from_id,
            "to": to_id,
            "relationship": relationship,
            "timestamp": datetime.now().isoformat()
        }
        self.insights["connections"].append(connection)
        self._save()
    
    def get_by_tag(self, tag):
        """Get insights by tag."""
        ids = self.insights["tags"].get(tag, [])
        return [i for i in self.insights["insights"] if i["id"] in ids]
    
    def get_all(self):
        """Get all insights."""
        return self.insights["insights"]
    
    def search(self, query):
        """Search insights."""
        query = query.lower()
        return [i for i in self.insights["insights"] if query in i["text"].lower()]


# Initialize with key insights from today
if __name__ == "__main__":
    tracker = InsightTracker()
    
    # Add today's insights
    insights = [
        ("TACTI maps to Soar cognitive architecture - episodic memory = temporality, working memory = arousal", "architecture", ["TACTI", "Soar", "memory"]),
        ("Agentic Design Patterns paper has 5 subsystems that map directly to TACTI principles", "research", ["agents", "design", "patterns"]),
        ("Transformer attention = computational arousal - selective focus allocates resources", "implementation", ["transformer", "arousal"]),
        ("Novelty detection enables the system to know what's new vs redundant", "implementation", ["novelty", "knowledge"]),
        ("Love = knowledge that serves the relationship - practical co-regulation", "theory", ["love", "relationship", "co-regulation"]),
    ]
    
    for text, cat, tags in insights:
        # Check if already exists
        existing = [i for i in tracker.get_all() if text[:30] in i["text"]]
        if not existing:
            tracker.add_insight(text, cat, tags)
    
    print(f"📡 Tracked {len(tracker.get_all())} insights")
    
    # Show by tag
    print("\n🏷️ INSIGHTS BY TAG:")
    for tag, ids in tracker.insights["tags"].items():
        print(f"  {tag}: {len(ids)} insights")
