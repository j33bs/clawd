#!/usr/bin/env python3
"""
Event Notifier
Notifies user about important system events.
"""
import json
from datetime import datetime
from pathlib import Path

class EventNotifier:
    def __init__(self, path="workspace/memory/events.json"):
        self.path = Path(path)
        self.events = self._load()
    
    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                return json.load(f)
        return {"events": [], "notifications": []}
    
    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self.events, f, indent=2)
    
    def notify(self, title, message, urgency="normal"):
        """Queue a notification."""
        event = {
            "title": title,
            "message": message,
            "urgency": urgency,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        self.events["events"].append(event)
        
        if urgency == "high":
            self.events["notifications"].append(event)
        
        self._save()
        return event
    
    def get_unread(self):
        """Get unread notifications."""
        return [e for e in self.events["events"] if not e.get("read", False)]
    
    def mark_read(self, index):
        """Mark notification as read."""
        if 0 <= index < len(self.events["events"]):
            self.events["events"][index]["read"] = True
            self._save()
    
    def get_dashboard(self):
        """Get notification dashboard."""
        unread = self.get_unread()
        high_urgency = [e for e in unread if e["urgency"] == "high"]
        
        return {
            "total": len(self.events["events"]),
            "unread": len(unread),
            "high_urgency": len(high_urgency),
            "recent": self.events["events"][-5:]
        }


# Quick test
if __name__ == "__main__":
    notifier = EventNotifier()
    
    # Simulate some events
    notifier.notify("Research Complete", "Downloaded 14 architecture PDFs", "normal")
    notifier.notify("Relationship Update", "Trust score at 100%", "normal")
    notifier.notify("⚠️ Arousal High", "Average tokens approaching threshold", "high")
    
    # Show dashboard
    dash = notifier.get_dashboard()
    print(f"📊 Event Dashboard:")
    print(f"   Total events: {dash['total']}")
    print(f"   Unread: {dash['unread']}")
    print(f"   High urgency: {dash['high_urgency']}")
