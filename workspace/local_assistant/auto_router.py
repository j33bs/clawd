#!/usr/bin/env python3
"""
Local Assistant Daily Automation
- Health check local model
- Route eligible tasks to local model
- Collect samples for learning
Run via cron: 0 * * * * (hourly)
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add workspace to path
REPO_ROOT = Path("/home/jeebs/src/clawd")
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from local_assistant.task_router import check_local_model, chat_local, route_task
from local_assistant.learning_pipeline import save_sample, count_samples

def run_health_check():
    """Verify local model is healthy"""
    healthy = check_local_model()
    status = "OK" if healthy else "DOWN"
    print(f"[{datetime.now(timezone.utc).isoformat()}] Local model: {status}")
    return healthy

def run_sample_collector():
    """Count collected samples"""
    total = count_samples()
    print(f"Learning samples collected: {total}")
    return total

def test_local_capabilities():
    """Test local model on sample tasks"""
    if not check_local_model():
        print("Model offline, skipping capability test")
        return None
    
    test_tasks = [
        ("Explain closures in JavaScript", "coding"),
        ("What is the capital of Australia?", "general"),
        ("Summarize: The quick brown fox jumps", "reasoning")
    ]
    
    results = []
    for prompt, expected_type in test_tasks:
        resp = chat_local(prompt, max_tokens=256)
        results.append({
            "task": prompt[:40],
            "type": expected_type,
            "success": resp is not None,
            "response": resp[:100] if resp else None
        })
        print(f"  {expected_type}: {'✓' if resp else '✗'}")
    
    return results

if __name__ == "__main__":
    print("=== Local Assistant Auto-Router ===")
    
    healthy = run_health_check()
    samples = run_sample_collector()
    
    if "--test" in sys.argv:
        results = test_local_capabilities()
        print(f"\nCapability test complete")
    
    print(f"\nTotal samples available for training: {samples}")
