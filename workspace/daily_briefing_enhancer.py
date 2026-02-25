#!/usr/bin/env python3
"""
Daily Briefing Enhancer
Uses TACTI modules to personalize daily briefing.
"""
import json
import sys
from pathlib import Path

# Add memory to path
sys.path.insert(0, str(Path(__file__).parent / "memory"))

from tacti_core import get_core

class BriefingEnhancer:
    def __init__(self):
        self.core = get_core()
    
    def get_personalization(self):
        health = self.core.get_relationship_health()
        
        if health["trust"] > 0.8:
            tone = "warm"
        elif health["trust"] > 0.5:
            tone = "neutral"
        else:
            tone = "gentle"
        
        return {
            "tone": tone,
            "trust": health["trust"],
            "attunement": health["attunement"]
        }
    
    def get_relationship_note(self):
        health = self.core.get_relationship_health()
        if health["total_interactions"] == 0:
            return None
        notes = []
        if health["trust"] > 0.9:
            notes.append("Strong trust")
        return " | ".join(notes) if notes else None
    
    def suggest_technique(self):
        health = self.core.get_relationship_health()
        if health["trust"] < 0.5:
            return "TACTI: Intersystemic Relationship Check"
        return None


if __name__ == "__main__":
    enhancer = BriefingEnhancer()
    print("Personalization:", enhancer.get_personalization())
    print("Relationship Note:", enhancer.get_relationship_note())
