#!/usr/bin/env python3
"""
TACTI Core - Unified Memory and State Management
Integrates all TACTI modules into a cohesive system.
"""
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from pattern_chunker import PatternChunker
from tacti_skill_evolution import SkillEvolution

# Import underlying modules for wrapper classes
import relationship_tracker as rt
import arousal_tracker as at

REPO_ROOT = Path(__file__).resolve().parents[2]


class RelationshipTracker:
    """Wrapper for relationship tracking functions."""
    
    def __init__(self):
        self.repo_root = REPO_ROOT
    
    def record_interaction(self, type, sentiment=0.5, resolution="success"):
        """Record an interaction with the user."""
        event = {
            "type": type,
            "sentiment": sentiment,
            "resolution": resolution
        }
        rt.update_from_event(event, repo_root=self.repo_root)
    
    def record_insight(self, insight):
        """Record an insight about the relationship."""
        # Store as a custom event
        event = {"type": "insight", "content": insight}
        rt.update_from_event(event, repo_root=self.repo_root)
    
    def get_health(self):
        """Get current relationship health."""
        state = rt.load_state(repo_root=self.repo_root)
        sessions = state.get("sessions", {})
        if not sessions:
            return {"health": 1.0, "sessions": 0}
        
        # Simple health metric
        total = sum(s.get("trust", 0.5) for s in sessions.values())
        return {
            "health": total / len(sessions) if sessions else 1.0,
            "sessions": len(sessions)
        }


class ArousalTracker:
    """Wrapper for arousal tracking functions."""
    
    def __init__(self):
        self.repo_root = REPO_ROOT
    
    def record_message(self, token_count=0, tool_calls=0, tool_failures=0):
        """Record message activity."""
        event = {
            "type": "message",
            "token_count": token_count,
            "tool_calls": tool_calls,
            "tool_failures": tool_failures
        }
        at.update_from_event(event, repo_root=self.repo_root)
    
    def get_state(self):
        """Get current arousal state."""
        state = at.load_state(repo_root=self.repo_root)
        sessions = state.get("sessions", {})
        if not sessions:
            return {"energy": 0.5, "sessions": 0}
        
        total = sum(s.get("energy", 0.5) for s in sessions.values())
        return {
            "energy": total / len(sessions) if sessions else 0.5,
            "sessions": len(sessions)
        }


class TacticCore:
    """Unified interface for TACTI state management."""
    
    def __init__(self):
        self.relationship = RelationshipTracker()
        self.arousal = ArousalTracker()
        self.chunker = PatternChunker()
        self.skill_evolution = SkillEvolution()
    
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
    
    # === SKILL EVOLUTION (cognee-skills loop) ===
    
    def record_skill_execution(self, skill_name: str, task: str, success: bool,
                                error: str = None, tool_failures: list = None):
        """Record skill execution for the self-improvement loop."""
        from tacti_skill_evolution import SkillExecution
        execution = SkillExecution(
            skill_name=skill_name,
            task=task,
            success=success,
            error=error,
            tool_failures=tool_failures or []
        )
        return self.skill_evolution.observe(execution)
    
    def inspect_skill(self, skill_name: str) -> dict:
        """Inspect skill for failure patterns."""
        return self.skill_evolution.inspect(skill_name)
    
    def amend_skill(self, skill_name: str, auto_approve: bool = False):
        """Propose and optionally apply skill amendment."""
        return self.skill_evolution.amend(skill_name, auto_approve)
    
    def evaluate_amendment(self, skill_name: str, success: bool, feedback: str = None):
        """Evaluate skill amendment effectiveness."""
        return self.skill_evolution.evaluate(skill_name, success, feedback)
    
    def get_skill_health(self) -> dict:
        """Get overall skill ecosystem health."""
        return self.skill_evolution.get_health_summary()
    
    # === INTEGRATION ===
    
    def full_status(self):
        """Get full system status."""
        return {
            "relationship": self.get_relationship_health(),
            "arousal": self.get_arousal_state(),
            "patterns_found": len(self.find_patterns()),
            "shortcuts": len(self.chunker.list_shortcuts()),
            "skill_health": self.get_skill_health()
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
