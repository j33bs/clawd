#!/usr/bin/env python3
"""
TACTI Unified CLI
Single entry point for all TACTI operations.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "research"))

def cmd_status(args):
    """Show system status."""
    from tacti_core import get_core
    from conversation_summarizer import ConversationSummarizer
    from insight_tracker import InsightTracker
    
    core = get_core()
    summarizer = ConversationSummarizer()
    tracker = InsightTracker()
    
    status = core.full_status()
    summary = summarizer.generate_summary()
    
    print("🧠 TACTI System Status")
    print("=" * 40)
    print(f"\n❤️ Relationship:")
    print(f"   Trust: {status['relationship']['trust']:.0%}")
    print(f"   Attunement: {status['relationship']['attunement']:.0%}")
    print(f"   Repairs: {status['relationship']['repairs']}")
    
    print(f"\n🧠 Arousal:")
    print(f"   State: {status['arousal']['state'].upper()}")
    print(f"   Avg tokens/msg: {status['arousal']['metrics']['avg_tokens_per_message']:.0f}")
    
    print(f"\n📊 Topics: {', '.join(summary['top_topics'][:5])}")
    print(f"🔬 Insights: {len(tracker.get_all())}")
    print(f"⚡ Patterns: {status['patterns_found']}")
    print(f"🔧 Shortcuts: {status['shortcuts']}")


def cmd_relationship(args):
    """Relationship commands."""
    from tacti_core import get_core
    from event_notifier import EventNotifier
    
    core = get_core()
    notifier = EventNotifier()
    health = core.get_relationship_health()
    
    print("❤️ Relationship Health")
    print("=" * 40)
    print(f"Trust: {health['trust']:.0%}")
    print(f"Attunement: {health['attunement']:.0%}")
    print(f"Repairs: {health['repairs']}")
    print(f"Total Interactions: {health['total_interactions']}")
    
    if args.record:
        sentiment = float(args.record)
        core.record_interaction("manual_check", sentiment)
        notifier.notify("Relationship Check-in", f"Manual check recorded with sentiment {sentiment}")
        print(f"\n✅ Recorded interaction (sentiment: {sentiment})")


def cmd_topics(args):
    """Show conversation topics."""
    from conversation_summarizer import ConversationSummarizer
    
    summarizer = ConversationSummarizer()
    summary = summarizer.generate_summary()
    
    print("📊 Recent Topics")
    print("=" * 40)
    for i, (topic, count) in enumerate(summary["topic_counts"].items(), 1):
        print(f"{i}. {topic}: {count}")
    
    if summary["decisions"]:
        print("\n✓ Recent Decisions:")
        for d in summary["decisions"][-3:]:
            print(f"   • {d[:70]}")


def cmd_insights(args):
    """Research insights."""
    from insight_tracker import InsightTracker
    
    tracker = InsightTracker()
    
    if args.tag:
        insights = tracker.get_by_tag(args.tag)
    else:
        insights = tracker.get_all()
    
    print(f"🔬 Insights ({len(insights)})")
    print("=" * 40)
    for i, insight in enumerate(insights, 1):
        print(f"{i}. [{insight['category']}] {insight['text'][:70]}")
        print(f"   Tags: {', '.join(insight['tags'])}")


def cmd_gaps(args):
    """Research gaps."""
    from gap_analyzer import GapAnalyzer
    
    analyzer = GapAnalyzer()
    analyzer.analyze()
    
    print("❌ Research Gaps")
    print("=" * 40)
    for topic, desc in analyzer.topics_missing:
        print(f"• {topic}: {desc}")


def main():
    parser = argparse.ArgumentParser(description="TACTI Unified CLI")
    subparsers = parser.add_subparsers()
    
    # Status
    subparsers.add_parser("status", help="Show system status")
    
    # Relationship
    rel_parser = subparsers.add_parser("relationship", help="Relationship health")
    rel_parser.add_argument("--record", metavar="SENTIMENT", help="Record interaction (0-1)")
    
    # Topics
    subparsers.add_parser("topics", help="Conversation topics")
    
    # Insights
    ins_parser = subparsers.add_parser("insights", help="Research insights")
    ins_parser.add_argument("--tag", help="Filter by tag")
    
    # Gaps
    subparsers.add_parser("gaps", help="Research gaps")
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    elif hasattr(args, 'record'):
        cmd_relationship(args)
    elif hasattr(args, 'tag'):
        cmd_insights(args)
    else:
        # Default to status
        cmd_status(args)


if __name__ == "__main__":
    main()
