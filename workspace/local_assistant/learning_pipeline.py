#!/usr/bin/env python3
"""
Local Assistant Learning Pipeline
Captures c_lawd responses to build training data for Qwen3.5-27B
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

REPO_ROOT = Path("/home/jeebs/src/clawd")
DATA_DIR = REPO_ROOT / "workspace" / "local_assistant" / "learning_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class InteractionSample:
    """One interaction sample for fine-tuning"""
    instruction: str
    response: str
    context: str  # system prompt or task description
    timestamp: str
    source: str  # "c_lawd" for now
    task_type: str  # "reasoning", "coding", "general"
    
def save_sample(instruction: str, response: str, context: str, task_type: str = "general"):
    """Save a learning sample"""
    sample = InteractionSample(
        instruction=instruction,
        response=response,
        context=context,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source="c_lawd",
        task_type=task_type
    )
    
    # Save to daily file
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = DATA_DIR / f"{date_str}.jsonl"
    
    with open(out_file, "a") as f:
        f.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")
    
    return out_file

def get_recent_samples(days: int = 1, limit: int = 50) -> list[InteractionSample]:
    """Get recent samples for inspection"""
    samples = []
    now = datetime.now(timezone.utc)
    
    for i in range(days):
        date = now.replace(day=now.day - i)
        date_str = date.strftime("%Y-%m-%d")
        file_path = DATA_DIR / f"{date_str}.jsonl"
        
        if file_path.exists():
            with open(file_path) as f:
                for line in f:
                    if line.strip():
                        samples.append(json.loads(line))
    
    return samples[-limit:]

def count_samples() -> int:
    """Total samples collected"""
    total = 0
    for f in DATA_DIR.glob("*.jsonl"):
        with open(f) as fp:
            total += sum(1 for line in fp if line.strip())
    return total

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "count":
            print(f"Total samples: {count_samples()}")
        elif sys.argv[1] == "recent":
            for s in get_recent_samples():
                print(f"[{s['task_type']}] {s['instruction'][:60]}...")
