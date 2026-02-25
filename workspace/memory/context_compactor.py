#!/usr/bin/env python3
"""
Context Compactor
Automatically compacts context when arousal gets too high.
"""
import json
from pathlib import Path
from datetime import datetime

class ContextCompactor:
    def __init__(self, arousal_tracker_path="workspace/memory/arousal_state.json"):
        self.arousal_path = Path(arousal_tracker_path)
        self.threshold_tokens = 8000  # Compact if avg > 8000
    
    def should_compact(self):
        """Check if context should be compacted."""
        if not self.arousal_path.exists():
            return False
        
        with open(self.arousal_path) as f:
            state = json.load(f)
        
        avg = state.get("metrics", {}).get("avg_tokens_per_message", 0)
        return avg > self.threshold_tokens
    
    def compact(self, session_context):
        """
        Compact session context.
        Returns: (compact_context, summary)
        """
        # Simple compaction: keep recent, summarize old
        if not session_context:
            return "", "No context to compact"
        
        lines = session_context.split("\n")
        if len(lines) < 20:
            return session_context, "Context too small to compact"
        
        # Keep first 5 and last 15 lines
        kept = "\n".join(lines[:5] + ["... [compacted]", ""] + lines[-15:])
        
        summary = f"Compacted {len(lines)} lines to {len(kept.split(chr(10)))} lines"
        
        return kept, summary
    
    def auto_check(self, session_context=None):
        """Check and optionally compact."""
        if self.should_compact():
            if session_context:
                compacted, summary = self.compact(session_context)
                return True, compacted, summary
            return True, None, "Would compact but no context provided"
        return False, None, "Context healthy"


if __name__ == "__main__":
    compactor = ContextCompactor()
    
    # Test
    should, context, msg = compactor.auto_check("line 1\nline 2\n" * 100)
    print(f"Should compact: {should}")
    print(f"Message: {msg}")
