#!/usr/bin/env python3
"""
TACTI Integration Test
Simulates how all modules work together.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "memory"))
sys.path.insert(0, str(Path(__file__).parent / "research"))

from tacti_core import get_core
from conversation_summarizer import ConversationSummarizer
from insight_tracker import InsightTracker
from gap_analyzer import GapAnalyzer
from context_compactor import ContextCompactor

def run_integration_test():
    """Run full system integration test."""
    print("🧪 TACTI Integration Test")
    print("=" * 50)
    
    # 1. Get core status
    core = get_core()
    print("\n1️⃣ Core Status:")
    status = core.full_status()
    print(f"   Relationship: Trust {status['relationship']['trust']:.0%}")
    print(f"   Arousal: {status['arousal']['state']}")
    
    # 2. Conversation summary
    print("\n2️⃣ Conversation Summary:")
    summarizer = ConversationSummarizer()
    summary = summarizer.generate_summary()
    print(f"   Top topics: {', '.join(summary['top_topics'][:3])}")
    
    # 3. Research insights
    print("\n3️⃣ Research Insights:")
    tracker = InsightTracker()
    print(f"   Total insights: {len(tracker.get_all())}")
    print(f"   Tags: {', '.join(list(tracker.insights['tags'].keys())[:5])}")
    
    # 4. Gap analysis
    print("\n4️⃣ Research Gaps:")
    analyzer = GapAnalyzer()
    analyzer.analyze()
    print(f"   Topics covered: {len(analyzer.topics_covered)}")
    print(f"   Gaps: {len(analyzer.topics_missing)}")
    
    # 5. Context health
    print("\n5️⃣ Context Health:")
    compactor = ContextCompactor()
    should_compact, _, msg = compactor.auto_check()
    print(f"   Should compact: {should_compact}")
    print(f"   Status: {msg}")
    
    # 6. System query
    print("\n6️⃣ Natural Query Test:")
    from system_query import query_system
    print(query_system("relationship"))
    
    print("\n✅ Integration test complete!")
    return True


if __name__ == "__main__":
    run_integration_test()
