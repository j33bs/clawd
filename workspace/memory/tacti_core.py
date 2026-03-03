#!/usr/bin/env python3
"""
TACTI Core - Unified Memory and State Management
Integrates all TACTI modules into a cohesive system.
"""
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from relationship_tracker import RelationshipTracker
from arousal_tracker import ArousalTracker
from pattern_chunker import PatternChunker

class TacticCore:
    """Unified interface for TACTI state management."""
    
    def __init__(self):
        self.relationship = RelationshipTracker()
        self.arousal = ArousalTracker()
        self.chunker = PatternChunker()
    
    # === RELATIONSHIP ===
    
    def record_interaction(self, type, sentiment=0.5, resolution="success"):
        """Record an interaction with the user."""
        self.relationship.record_interaction(type, sentiment, resolution)
    
    def record_insight(self, insight):
        """Record an insight about the relationship."""
        self.relationship.record_insight(insight)
    
    def get_relationship_health(self):
        """Get current relationship health."""
        return self.relationship.get_health()
    
    # === AROUSAL ===
    
    def update_arousal(self, token_count=0, tool_calls=0, tool_failures=0):
        """Update arousal state based on activity."""
        self.arousal.record_message(token_count, tool_calls, tool_failures)
    
    def get_arousal_state(self):
        """Get current arousal state."""
        return self.arousal.get_state()
    
    # === PATTERNS ===
    
    def find_patterns(self, min_freq=2):
        """Find patterns in recent sessions."""
        return self.chunker.find_patterns(min_frequency=min_freq)
    
    def match_shortcut(self, text):
        """Check if text matches a shortcut."""
        return self.chunker.match_shortcut(text)
    
    # === INTEGRATION ===
    
    def full_status(self):
        """Get full system status."""
        return {
            "relationship": self.get_relationship_health(),
            "arousal": self.get_arousal_state(),
            "patterns_found": len(self.find_patterns()),
            "shortcuts": len(self.chunker.list_shortcuts())
        }


# Singleton instance
_core = None

def get_core():
    global _core
    if _core is None:
        _core = TacticCore()
    return _core


if __name__ == "__main__":
    core = get_core()
    print("TACTI Core Status:")
    import json
    print(json.dumps(core.full_status(), indent=2))
