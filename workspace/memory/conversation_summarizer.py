#!/usr/bin/env python3
"""
Conversation Summarizer
Extracts key insights and topics from conversation history.
"""
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

class ConversationSummarizer:
    def __init__(self, memory_dir="memory/"):
        self.memory_dir = Path(memory_dir)
    
    def extract_topics(self, days=7):
        """Extract common topics from recent memory."""
        topics = Counter()
        
        today = datetime.now()
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            memory_file = self.memory_dir / f"{date_str}.md"
            
            if memory_file.exists():
                content = memory_file.read_text()
                
                # Simple keyword extraction
                words = re.findall(r'\b[A-Z][a-z]+\b', content)
                # Filter common words
                skip = {'The', 'This', 'That', 'What', 'When', 'Where', 'Why', 'How',
                       'From', 'With', 'Using', 'Added', 'Created', 'Updated'}
                words = [w for w in words if w not in skip and len(w) > 3]
                topics.update(words)
        
        return topics.most_common(20)
    
    def extract_decisions(self, days=7):
        """Extract key decisions from memory."""
        decisions = []
        
        today = datetime.now()
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            memory_file = self.memory_dir / f"{date_str}.md"
            
            if memory_file.exists():
                content = memory_file.read_text()
                
                # Look for decision patterns
                lines = content.split("\n")
                for line in lines:
                    if any(kw in line.lower() for kw in ["decided", "agreed", "will", "changed", "update"]):
                        if len(line) > 20 and len(line) < 200:
                            decisions.append(line.strip())
        
        return decisions
    
    def extract_questions(self, days=7):
        """Extract questions the user asked."""
        questions = []
        
        today = datetime.now()
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            memory_file = self.memory_dir / f"{date_str}.md"
            
            if memory_file.exists():
                content = memory_file.read_text()
                
                # Find lines with ?
                for line in content.split("\n"):
                    if "?" in line and len(line) > 15:
                        questions.append(line.strip())
        
        return questions[-20:]  # Last 20
    
    def generate_summary(self):
        """Generate a conversation summary."""
        topics = self.extract_topics()
        decisions = self.extract_decisions()
        questions = self.extract_questions()
        
        return {
            "top_topics": [t[0] for t in topics[:10]],
            "decisions": decisions[-5:],
            "recent_questions": questions[-5:],
            "topic_counts": dict(topics[:10])
        }


if __name__ == "__main__":
    summarizer = ConversationSummarizer()
    summary = summarizer.generate_summary()
    
    print("📊 CONVERSATION SUMMARY")
    print("=" * 40)
    print("\n🔥 TOP TOPICS:")
    for topic, count in summary["topic_counts"].items():
        print(f"  {topic}: {count}")
    
    if summary["decisions"]:
        print("\n✓ KEY DECISIONS:")
        for d in summary["decisions"]:
            print(f"  • {d[:80]}")
    
    if summary["recent_questions"]:
        print("\n❓ RECENT QUESTIONS:")
        for q in summary["recent_questions"]:
            print(f"  • {q[:80]}")
