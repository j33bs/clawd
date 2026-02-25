#!/usr/bin/env python3
"""
Research Suggester
Suggests research directions based on gaps and user interests.
"""
import random

# Gaps from gap analyzer
GAPS = [
    ("Embodied Cognition", "How agents perceive and act in the world", "robotics, perception"),
    ("Theory of Mind", "Understanding other agents' mental states", "multi-agent, social"),
    ("Meta-Learning", "Learning to learn", "optimization, adaptation"),
    ("Continual Learning", "Learning without forgetting", "catastrophic forgetting"),
    ("Causal Inference", "Understanding cause and effect", "causality, reasoning"),
    ("World Models", "Internal representations of reality", "simulations, RL"),
    ("Self-Talk", "Internal dialogue and reasoning", "CoT, reflection"),
    ("Consciousness", "Awareness and experience", "IIT, awareness")
]

# User interests (from memory)
INTERESTS = ["TACTI", "IPNB", "IFS", "memory", "novelty", "love", "relationship"]

def suggest():
    """Suggest research directions."""
    suggestions = []
    
    for gap, desc, tags in GAPS:
        # Calculate relevance to user interests
        relevance = len(set(tags) & set(INTERESTS)) / len(tags)
        
        if relevance > 0 or random.random() > 0.5:
            suggestions.append({
                "topic": gap,
                "description": desc,
                "tags": tags,
                "relevance": relevance
            })
    
    # Sort by relevance
    suggestions.sort(key=lambda x: x["relevance"], reverse=True)
    
    return suggestions[:5]

if __name__ == "__main__":
    print("🔬 RESEARCH SUGGESTIONS")
    print("=" * 40)
    print(f"Based on your interests: {', '.join(INTERESTS)}")
    print()
    
    for i, s in enumerate(suggest(), 1):
        relevance = "⭐" * int(s["relevance"] * 3)
        print(f"{i}. {s['topic']} {relevance}")
        print(f"   {s['description']}")
        print()
