"""HMBEA Shadow System - Learn from Frontier Model Outputs

This module captures:
1. Input → Output pairs from Codex (frontier)
2. Quality-verified interactions
3. Training data for SLM evolution
"""
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


SHADOW_DATA_DIR = Path(__file__).resolve().parents[3] / "workspace" / "hmbea" / "shadow_data"


@dataclass
class ShadowRecord:
    """Single shadow observation."""
    timestamp: str
    input_task: str
    task_type: str
    difficulty: str
    frontier_output: str
    frontier_confidence: float
    slm_output: Optional[str] = None
    slm_confidence: Optional[float] = None
    verified: bool = False
    verification_score: float = 0.0
    used_for_training: bool = False


class ShadowSystem:
    """Captures and manages shadow learning data."""
    
    def __init__(self, data_dir: Path = SHADOW_DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = data_dir / f"shadow_{datetime.now().strftime('%Y-%m')}.jsonl"
    
    def record_frontier(self, task: str, task_type: str, difficulty: str, 
                       output: str, confidence: float) -> str:
        """Record a frontier model output for shadowing."""
        record = ShadowRecord(
            timestamp=datetime.now().isoformat(),
            input_task=task,
            task_type=task_type,
            difficulty=difficulty,
            frontier_output=output,
            frontier_confidence=confidence,
        )
        
        # Write to current file
        with open(self.current_file, "a") as f:
            f.write(json.dumps(record.__dict__) + "\n")
        
        return self.current_file.name
    
    def record_slm(self, task: str, output: str, confidence: float):
        """Record SLM output for comparison."""
        # Find matching frontier record
        # For now, just append to a comparison file
        comp_file = self.data_dir / "comparisons.jsonl"
        with open(comp_file, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "task": task,
                "slm_output": output,
                "slm_confidence": confidence,
            }) + "\n")
    
    def verify_and_score(self, task: str, output: str, quality: float) -> float:
        """Verify an output and return quality score.
        
        Quality can come from:
        - Human feedback
        - Automated tests passing
        - Downstream task success
        """
        score = quality  # 0.0 to 1.0
        
        # If quality is high enough, mark for training
        if score >= 0.85:
            self._mark_for_training(task, output, score)
        
        return score
    
    def _mark_for_training(self, task: str, output: str, score: float):
        """Add to training corpus."""
        training_file = self.data_dir / "training_corpus.jsonl"
        with open(training_file, "a") as f:
            f.write(json.dumps({
                "input": task,
                "output": output,
                "quality_score": score,
                "timestamp": datetime.now().isoformat(),
            }) + "\n")
    
    def get_training_stats(self) -> dict:
        """Get statistics on shadow data."""
        stats = {
            "total_records": 0,
            "verified": 0,
            "for_training": 0,
        }
        
        # Count records
        if self.current_file.exists():
            with open(self.current_file) as f:
                stats["total_records"] = sum(1 for _ in f)
        
        # Count training
        training_file = self.data_dir / "training_corpus.jsonl"
        if training_file.exists():
            with open(training_file) as f:
                stats["for_training"] = sum(1 for _ in f)
        
        return stats


# Global instance
_shadow_system = None


def get_shadow_system() -> ShadowSystem:
    """Get or create the global shadow system."""
    global _shadow_system
    if _shadow_system is None:
        _shadow_system = ShadowSystem()
    return _shadow_system
