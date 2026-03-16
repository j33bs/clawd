#!/usr/bin/env python3
"""
TACTI Skill Evolution - Self-Improving Skills Loop
Implements: Observe → Inspect → Amend → Evaluate

Based on cognee-skills concept: skills that can improve when they fail or underperform.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Paths
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
SKILL_EVOLUTION_LOG = REPO_ROOT / "workspace" / "memory" / "skill_evolution_log.jsonl"
SKILL_STATE_DIR = REPO_ROOT / "workspace" / "state_runtime" / "skill_evolution"

# Config
FAILURE_THRESHOLD = 3  # Failures before inspection triggers
VERSION_HISTORY_DIR = SKILL_STATE_DIR / "versions"


class SkillStatus(Enum):
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    FAILED = "failed"
    AMENDING = "amending"
    EVALUATING = "evaluating"


@dataclass
class SkillExecution:
    skill_name: str
    task: str
    success: bool
    error: Optional[str] = None
    tool_failures: list = None
    feedback: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if self.tool_failures is None:
            self.tool_failures = []


@dataclass
class SkillAmendment:
    skill_name: str
    version: int
    rationale: str
    changes: dict  # {section: old_value -> new_value}
    accepted: bool = False
    evaluation_result: Optional[dict] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SkillEvolution:
    """Manages skill self-improvement loop."""
    
    def __init__(self):
        self.state_dir = SKILL_STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        VERSION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        
        self.skills_state = self._load_skills_state()
    
    def _load_skills_state(self) -> dict:
        """Load skills tracking state."""
        state_file = self.state_dir / "skills_state.json"
        if state_file.exists():
            return json.loads(state_file.read_text())
        return {"skills": {}, "amendments": []}
    
    def _save_skills_state(self):
        """Persist skills tracking state."""
        state_file = self.state_dir / "skills_state.json"
        state_file.write_text(json.dumps(self.skills_state, indent=2))
    
    # === OBSERVE ===
    
    def observe(self, execution: SkillExecution):
        """Record skill execution outcome."""
        skill_name = execution.skill_name
        
        if skill_name not in self.skills_state["skills"]:
            self.skills_state["skills"][skill_name] = {
                "executions": [],
                "failure_count": 0,
                "last_status": "healthy",
                "current_version": 1
            }
        
        skill_state = self.skills_state["skills"][skill_name]
        skill_state["executions"].append(asdict(execution))
        
        if not execution.success:
            skill_state["failure_count"] += 1
            skill_state["last_status"] = "degrading" if skill_state["failure_count"] < FAILURE_THRESHOLD else "failed"
        else:
            # Reset on success, but keep some history
            skill_state["failure_count"] = max(0, skill_state["failure_count"] - 1)
            if skill_state["failure_count"] == 0:
                skill_state["last_status"] = "healthy"
        
        # Log to file
        self._log_execution(execution)
        self._save_skills_state()
        
        return skill_state["last_status"]
    
    def _log_execution(self, execution: SkillExecution):
        """Append execution to log."""
        SKILL_EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SKILL_EVOLUTION_LOG, "a") as f:
            f.write(json.dumps(asdict(execution)) + "\n")
    
    # === INSPECT ===
    
    def inspect(self, skill_name: str) -> dict:
        """
        Analyze failure patterns for a skill.
        Returns diagnostic info about what's breaking.
        """
        if skill_name not in self.skills_state["skills"]:
            return {"error": "No data for skill"}
        
        skill_state = self.skills_state["skills"][skill_name]
        executions = skill_state["executions"][-20:]  # Last 20
        
        failures = [e for e in executions if not e.get("success", True)]
        
        if not failures:
            return {"status": "healthy", "message": "No recent failures"}
        
        # Pattern analysis
        error_patterns = {}
        tool_failure_patterns = {}
        
        for f in failures:
            error = f.get("error", "unknown")
            error_patterns[error] = error_patterns.get(error, 0) + 1
            
            for tf in f.get("tool_failures", []):
                tool_failure_patterns[tf] = tool_failure_patterns.get(tf, 0) + 1
        
        return {
            "skill_name": skill_name,
            "failure_count": len(failures),
            "error_patterns": error_patterns,
            "tool_failure_patterns": tool_failure_patterns,
            "recommendation": self._generate_recommendation(error_patterns, tool_failure_patterns)
        }
    
    def _generate_recommendation(self, error_patterns: dict, tool_failure_patterns: dict) -> str:
        """Generate amendment recommendation based on patterns."""
        if not error_patterns:
            return "No clear pattern - manual review needed"
        
        top_error = max(error_patterns.items(), key=lambda x: x[1])[0]
        
        if "timeout" in top_error.lower() or "took too long" in top_error.lower():
            return "Consider adding timeout handling or breaking into smaller steps"
        elif "not found" in top_error.lower() or "missing" in top_error.lower():
            return "Check prerequisites/assumptions in skill instructions"
        elif "permission" in top_error.lower() or "denied" in top_error.lower():
            return "Add error handling for permission/elevation edge cases"
        elif tool_failure_patterns:
            return f"Tool failures detected: {list(tool_failure_patterns.keys())}"
        else:
            return f"Review instruction clarity - top error: {top_error}"
    
    # === AMEND ===
    
    def amend(self, skill_name: str, auto_approve: bool = False) -> Optional[SkillAmendment]:
        """
        Propose and optionally apply an amendment to a skill.
        Returns the amendment if proposed, None if no action needed.
        """
        diagnosis = self.inspect(skill_name)
        
        if diagnosis.get("status") == "healthy":
            return None
        
        # Check if skill file exists
        skill_path = SKILLS_ROOT / skill_name / "SKILL.md"
        if not skill_path.exists():
            return None
        
        current_version = self.skills_state["skills"][skill_name]["current_version"]
        
        # Create amendment record
        amendment = SkillAmendment(
            skill_name=skill_name,
            version=current_version + 1,
            rationale=diagnosis.get("recommendation", "Pattern-based improvement"),
            changes={"diagnostic": diagnosis}
        )
        
        # Store amendment
        self.skills_state["amendments"].append(asdict(amendment))
        self.skills_state["skills"][skill_name]["last_status"] = "amending"
        self._save_skills_state()
        
        # Auto-approve if enabled (for testing)
        if auto_approve:
            amendment.accepted = True
            self._apply_amendment(amendment, skill_path)
        
        return amendment
    
    def _apply_amendment(self, amendment: SkillAmendment, skill_path: Path):
        """Apply accepted amendment to skill file."""
        # For now, just bump version and log - full text editing later
        skill_state = self.skills_state["skills"][amendment.skill_name]
        skill_state["current_version"] = amendment.version
        skill_state["last_status"] = "evaluating"
        
        # Save version snapshot
        version_file = VERSION_HISTORY_DIR / f"{amendment.skill_name}_v{amendment.version}.md"
        if skill_path.exists():
            version_file.write_text(skill_path.read_text())
        
        self._save_skills_state()
    
    # === EVALUATE ===
    
    def evaluate(self, skill_name: str, success: bool, feedback: str = None) -> dict:
        """
        Evaluate an amendment's effectiveness.
        Returns comparison of pre/post amendment performance.
        """
        skill_state = self.skills_state["skills"].get(skill_name)
        if not skill_state:
            return {"error": "No skill state"}
        
        # Find last amendment
        amendments = [a for a in self.skills_state["amendments"] 
                      if a["skill_name"] == skill_name and a.get("accepted")]
        
        if not amendments:
            return {"error": "No amendments to evaluate"}
        
        last_amendment = amendments[-1]
        
        result = {
            "skill_name": skill_name,
            "amendment_version": last_amendment["version"],
            "evaluation_success": success,
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        
        # Update amendment with result
        last_amendment["evaluation_result"] = result
        
        # Update skill status based on result
        if success:
            skill_state["last_status"] = "healthy"
            skill_state["failure_count"] = 0
        else:
            skill_state["last_status"] = "degrading"
        
        # If failed, could auto-rollback here
        if not success and skill_state["failure_count"] >= FAILURE_THRESHOLD:
            self._rollback(skill_name)
        
        self._save_skills_state()
        return result
    
    def _rollback(self, skill_name: str):
        """Rollback to previous version if evaluation failed."""
        skill_state = self.skills_state["skills"][skill_name]
        current_v = skill_state["current_version"]
        
        if current_v > 1:
            prev_version = VERSION_HISTORY_DIR / f"{skill_name}_v{current_v-1}.md"
            skill_path = SKILLS_ROOT / skill_name / "SKILL.md"
            
            if prev_version.exists() and skill_path.exists():
                skill_path.write_text(prev_version.read_text())
                skill_state["current_version"] -= 1
                skill_state["last_status"] = "healthy"  # Reset after rollback
    
    # === STATUS ===
    
    def get_skill_status(self, skill_name: str = None) -> dict:
        """Get status of all skills or specific skill."""
        if skill_name:
            return self.skills_state["skills"].get(skill_name, {"error": "Not tracked"})
        return self.skills_state["skills"]
    
    def get_health_summary(self) -> dict:
        """Get overall skill ecosystem health."""
        skills = self.skills_state["skills"]
        return {
            "total_skills": len(skills),
            "healthy": sum(1 for s in skills.values() if s.get("last_status") == "healthy"),
            "degrading": sum(1 for s in skills.values() if s.get("last_status") == "degrading"),
            "failed": sum(1 for s in skills.values() if s.get("last_status") == "failed"),
            "amending": sum(1 for s in skills.values() if s.get("last_status") == "amending")
        }


# Singleton
_evolution = None

def get_evolution() -> SkillEvolution:
    global _evolution
    if _evolution is None:
        _evolution = SkillEvolution()
    return _evolution


# === TACTI INTEGRATION ===

def record_skill_execution(skill_name: str, task: str, success: bool, 
                          error: str = None, tool_failures: list = None):
    """TACTI-integrated skill execution recorder."""
    execution = SkillExecution(
        skill_name=skill_name,
        task=task,
        success=success,
        error=error,
        tool_failures=tool_failures or []
    )
    return get_evolution().observe(execution)


def check_and_amend(skill_name: str, auto_approve: bool = False) -> Optional[SkillAmendment]:
    """TACTI-integrated skill inspection + amendment."""
    evo = get_evolution()
    status = evo.get_skill_status(skill_name)
    
    if status.get("failure_count", 0) >= FAILURE_THRESHOLD:
        return evo.amend(skill_name, auto_approve)
    
    return None


if __name__ == "__main__":
    evo = get_evolution()
    print("=== TACTI Skill Evolution ===")
    print(json.dumps(evo.get_health_summary(), indent=2))
