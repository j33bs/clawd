#!/usr/bin/env python3
"""
System Query - Natural language interface to TACTI system state
"""
import sys
from pathlib import Path

# Add memory to path
sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "research"))

from tacti_core import get_core
from conversation_summarizer import ConversationSummarizer
from insight_tracker import InsightTracker

def query_system(query):
    """Answer natural language queries about the system."""
    query = query.lower()
    core = get_core()
    
    # Relationship queries
    if any(w in query for w in ["relationship", "trust", "bond", "connection"]):
        health = core.get_relationship_health()
        return f"""
❤️ Relationship Status:
  Trust: {health['trust']:.0%}
  Attunement: {health['attunement']:.0%}
  Repairs: {health['repairs']}
  Interactions: {health['total_interactions']}
        """
    
    # Arousal queries
    if any(w in query for w in ["arousal", "state", "energy", "active", "focused"]):
        arousal = core.get_arousal_state()
        return f"""
🧠 Arousal State: {arousal['state'].upper()}
  Avg tokens/msg: {arousal['metrics']['avg_tokens_per_message']:.0f}
  Messages: {arousal['metrics']['total_messages']}
  Tool failures: {arousal['metrics']['tool_failures']}
        """
    
    # Topic queries
    if any(w in query for w in ["topic", "what have we talked about", "conversation"]):
        summarizer = ConversationSummarizer()
        summary = summarizer.generate_summary()
        topics = ", ".join(summary["top_topics"][:5])
        return f"""
📊 Recent Topics: {topics}
  Decisions: {len(summary['decisions'])}
  Questions: {len(summary['recent_questions'])}
        """
    
    # Research queries
    if any(w in query for w in ["research", "insight", "learned"]):
        tracker = InsightTracker()
        insights = tracker.get_all()
        tags = list(tracker.insights["tags"].keys())
        return f"""
🔬 Research Insights: {len(insights)}
  Tags: {', '.join(tags[:10])}
        """
    
    # Full status
    if any(w in query for w in ["status", "everything", "all"]):
        status = core.full_status()
        return f"""
📈 Full System Status:
  Relationship: Trust {status['relationship']['trust']:.0%}, Attunement {status['relationship']['attunement']:.0%}
  Arousal: {status['arousal']['state']} (avg {status['arousal']['metrics']['avg_tokens_per_message']:.0f} tokens/msg)
  Patterns Found: {status['patterns_found']}
  Shortcuts: {status['shortcuts']}
        """
    
    return "I can answer questions about: relationship, arousal, topics, research, or full status. Try: 'system status' or 'how's our relationship?'"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python system_query.py '<question>'")
        print("\nExamples:")
        print("  python system_query.py 'how's the relationship?'")
        print("  python system_query.py 'what's the arousal state?'")
        print("  python system_query.py 'system status'")
        sys.exit(1)
    
    query = ' '.join(sys.argv[1:])
    print(query_system(query))
