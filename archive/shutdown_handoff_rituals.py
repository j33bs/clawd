#!/usr/bin/env python3
"""
Deliberate Shutdown and Handoff Rituals System
Implements explicit "end-of-work" states where the agent summarizes what is done,
what is uncertain, and what the next human action should be
"""

import json
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import threading


@dataclass
class WorkSummary:
    """Summary of completed work"""
    completed_tasks: List[str]
    in_progress_tasks: List[str]
    blocked_tasks: List[str]
    achievements: List[str]
    metrics: Dict[str, Any]


@dataclass
class UncertaintyReport:
    """Report of uncertainties and unknowns"""
    open_questions: List[str]
    ambiguous_requirements: List[str]
    missing_information: List[str]
    risk_factors: List[str]
    confidence_levels: Dict[str, float]  # 0.0 to 1.0


@dataclass
class NextActionRecommendation:
    """Recommended next actions for human"""
    priority_actions: List[str]
    optional_followups: List[str]
    decision_points: List[str]
    resource_needs: List[str]
    timeline_suggestions: List[str]


@dataclass
class HandoffState:
    """Complete handoff state"""
    timestamp: float
    work_summary: WorkSummary
    uncertainty_report: UncertaintyReport
    next_actions: NextActionRecommendation
    context_snapshot: Dict[str, Any]
    recommendations_confidence: float  # 0.0 to 1.0
    session_metadata: Dict[str, Any]


class ShutdownRitualManager:
    """
    Manages deliberate shutdown and handoff rituals
    Ensures proper closure of work sessions with clear next steps
    """
    
    def __init__(self):
        self.work_tracker = {}
        self.uncertainty_tracker = {}
        self.context_snapshot = {}
        self.session_start_time = time.time()
        self.tasks_completed = []
        self.tasks_in_progress = []
        self.tasks_blocked = []
        self.uncertainties = []
        self.metrics = {}
        self.recommendations = []
        self.shutdown_callbacks = []
    
    def add_work_completed(self, task_description: str, achievement: Optional[str] = None):
        """Add a completed task to the tracker"""
        self.tasks_completed.append(task_description)
        if achievement:
            if 'achievements' not in self.metrics:
                self.metrics['achievements'] = []
            self.metrics['achievements'].append(achievement)
    
    def mark_task_in_progress(self, task_description: str):
        """Mark a task as currently in progress"""
        self.tasks_in_progress.append(task_description)
    
    def mark_task_blocked(self, task_description: str, reason: str):
        """Mark a task as blocked with a reason"""
        self.tasks_blocked.append({
            'task': task_description,
            'reason': reason
        })
    
    def add_uncertainty(self, question: str, confidence: float = 0.5):
        """Add an uncertainty or open question"""
        self.uncertainties.append({
            'question': question,
            'confidence': confidence,
            'timestamp': time.time()
        })
    
    def update_metric(self, metric_name: str, value: Any):
        """Update a session metric"""
        self.metrics[metric_name] = value
    
    def register_shutdown_callback(self, callback: Callable[[], None]):
        """Register a callback to be called during shutdown"""
        self.shutdown_callbacks.append(callback)
    
    def create_work_summary(self) -> WorkSummary:
        """Create a summary of work done"""
        return WorkSummary(
            completed_tasks=self.tasks_completed.copy(),
            in_progress_tasks=[t if isinstance(t, str) else t['task'] for t in self.tasks_in_progress],
            blocked_tasks=[t['task'] if isinstance(t, dict) else t for t in self.tasks_blocked],
            achievements=self.metrics.get('achievements', []),
            metrics=self.metrics.copy()
        )
    
    def create_uncertainty_report(self) -> UncertaintyReport:
        """Create a report of uncertainties"""
        open_questions = [u['question'] for u in self.uncertainties]
        confidence_levels = {u['question']: u['confidence'] for u in self.uncertainties}
        
        return UncertaintyReport(
            open_questions=open_questions,
            ambiguous_requirements=[],  # Would be populated based on specific context
            missing_information=[],     # Would be populated based on specific context
            risk_factors=self._identify_risk_factors(),
            confidence_levels=confidence_levels
        )
    
    def _identify_risk_factors(self) -> List[str]:
        """Identify potential risk factors from the work done"""
        risks = []
        
        # Time-based risks
        session_duration = time.time() - self.session_start_time
        if session_duration > 3600:  # More than 1 hour
            risks.append("Extended session duration may lead to fatigue")
        
        # Task-based risks
        if len(self.tasks_blocked) > len(self.tasks_completed) * 0.5:  # More than 50% blocked
            risks.append("High proportion of blocked tasks indicates potential systemic issues")
        
        # Uncertainty-based risks
        low_confidence_items = [u for u in self.uncertainties if u['confidence'] < 0.3]
        if len(low_confidence_items) > 3:
            risks.append("Multiple low-confidence assessments indicate knowledge gaps")
        
        return risks
    
    def create_next_action_recommendations(self) -> NextActionRecommendation:
        """Create recommendations for next human actions"""
        priority_actions = []
        optional_followups = []
        decision_points = []
        resource_needs = []
        timeline_suggestions = []
        
        # Priority actions based on blocked tasks
        for blocked_task in self.tasks_blocked:
            if isinstance(blocked_task, dict):
                priority_actions.append(f"Resolve blocking issue for: {blocked_task['task']} ({blocked_task['reason']})")
        
        # Priority actions based on open questions with low confidence
        low_confidence_questions = [
            u['question'] for u in self.uncertainties 
            if u['confidence'] < 0.4
        ]
        for question in low_confidence_questions:
            priority_actions.append(f"Clarify or investigate: {question}")
        
        # Optional followups for completed tasks
        for task in self.tasks_completed[-3:]:  # Last 3 completed tasks
            optional_followups.append(f"Review and validate completion of: {task}")
        
        # Decision points for ambiguous areas
        if self.uncertainties:
            decision_points.append(f"Address {len(self.uncertainties)} open questions before proceeding")
        
        # Resource needs
        if len(self.tasks_blocked) > 2:
            resource_needs.append("Additional resources or information needed to unblock tasks")
        
        # Timeline suggestions
        session_duration_hours = round((time.time() - self.session_start_time) / 3600, 1)
        if session_duration_hours > 1:
            timeline_suggestions.append(f"Consider breaking work into smaller sessions (current session: {session_duration_hours} hours)")
        
        return NextActionRecommendation(
            priority_actions=priority_actions,
            optional_followups=optional_followups,
            decision_points=decision_points,
            resource_needs=resource_needs,
            timeline_suggestions=timeline_suggestions
        )
    
    def execute_shutdown_ritual(self, context_snapshot: Optional[Dict[str, Any]] = None) -> HandoffState:
        """Execute the shutdown ritual and return a complete handoff state"""
        # Execute registered callbacks
        for callback in self.shutdown_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Shutdown callback error: {e}")
        
        # Create the handoff state
        handoff_state = HandoffState(
            timestamp=time.time(),
            work_summary=self.create_work_summary(),
            uncertainty_report=self.create_uncertainty_report(),
            next_actions=self.create_next_action_recommendations(),
            context_snapshot=context_snapshot or self.context_snapshot,
            recommendations_confidence=0.8,  # High confidence in basic recommendations
            session_metadata={
                'start_time': self.session_start_time,
                'duration_seconds': time.time() - self.session_start_time,
                'total_tasks_tracked': len(self.tasks_completed) + len(self.tasks_in_progress) + len(self.tasks_blocked),
                'uncertainty_count': len(self.uncertainties)
            }
        )
        
        # Print summary for immediate feedback
        self._print_handoff_summary(handoff_state)
        
        # Clear the session state (prepare for next session)
        self._reset_session()
        
        return handoff_state
    
    def _print_handoff_summary(self, handoff_state: HandoffState):
        """Print a summary of the handoff state"""
        print("\n" + "="*60)
        print("CloseOperation Ritual Complete")
        print("="*60)
        
        ws = handoff_state.work_summary
        ur = handoff_state.uncertainty_report
        na = handoff_state.next_actions
        
        print(f"🕒 Session Duration: {handoff_state.session_metadata['duration_seconds']:.1f}s")
        print(f"✅ Tasks Completed: {len(ws.completed_tasks)}")
        print(f"🔄 Tasks In Progress: {len(ws.in_progress_tasks)}")
        print(f"🚫 Tasks Blocked: {len(ws.blocked_tasks)}")
        print(f"❓ Open Questions: {len(ur.open_questions)}")
        
        print(f"\n📋 WORK SUMMARY:")
        if ws.completed_tasks:
            for i, task in enumerate(ws.completed_tasks[-3:], 1):  # Last 3
                print(f"  {i}. ✅ {task}")
        
        print(f"\n⚠️  UNCERTAINTIES & QUESTIONS:")
        if ur.open_questions:
            for i, question in enumerate(ur.open_questions[:3], 1):  # First 3
                conf = ur.confidence_levels.get(question, 0.5)
                status = "🔍" if conf < 0.5 else "💡"
                print(f"  {i}. {status} {question} (conf: {conf:.1f})")
        
        print(f"\n🚀 NEXT ACTIONS FOR HUMAN:")
        if na.priority_actions:
            print("  PRIORITY:")
            for i, action in enumerate(na.priority_actions[:3], 1):  # First 3 priorities
                print(f"    {i}. ⚡ {action}")
        
        if na.decision_points:
            print("  DECISIONS NEEDED:")
            for i, decision in enumerate(na.decision_points, 1):
                print(f"    {i}. 🤔 {decision}")
        
        if na.optional_followups:
            print("  OPTIONAL FOLLOWUPS:")
            for i, followup in enumerate(na.optional_followups[:2], 1):  # First 2
                print(f"    {i}. ➕ {followup}")
        
        if ur.risk_factors:
            print("  ⚠️  RISK FACTORS:")
            for i, risk in enumerate(ur.risk_factors, 1):
                print(f"    {i}. {risk}")
        
        print("="*60)
    
    def _reset_session(self):
        """Reset session state for next session"""
        self.tasks_completed = []
        self.tasks_in_progress = []
        self.tasks_blocked = []
        self.uncertainties = []
        self.metrics = {}
        self.session_start_time = time.time()
    
    def save_handoff_state(self, handoff_state: HandoffState, filename: str = None):
        """Save the handoff state to a file"""
        if not filename:
            timestamp = datetime.fromtimestamp(handoff_state.timestamp).strftime("%Y%m%d_%H%M%S")
            filename = f"handoff_state_{timestamp}.json"
        
        # Convert to serializable format
        state_dict = {
            'timestamp': handoff_state.timestamp,
            'work_summary': {
                'completed_tasks': handoff_state.work_summary.completed_tasks,
                'in_progress_tasks': handoff_state.work_summary.in_progress_tasks,
                'blocked_tasks': handoff_state.work_summary.blocked_tasks,
                'achievements': handoff_state.work_summary.achievements,
                'metrics': handoff_state.work_summary.metrics
            },
            'uncertainty_report': {
                'open_questions': handoff_state.uncertainty_report.open_questions,
                'ambiguous_requirements': handoff_state.uncertainty_report.ambiguous_requirements,
                'missing_information': handoff_state.uncertainty_report.missing_information,
                'risk_factors': handoff_state.uncertainty_report.risk_factors,
                'confidence_levels': handoff_state.uncertainty_report.confidence_levels
            },
            'next_actions': {
                'priority_actions': handoff_state.next_actions.priority_actions,
                'optional_followups': handoff_state.next_actions.optional_followups,
                'decision_points': handoff_state.next_actions.decision_points,
                'resource_needs': handoff_state.next_actions.resource_needs,
                'timeline_suggestions': handoff_state.next_actions.timeline_suggestions
            },
            'context_snapshot': handoff_state.context_snapshot,
            'recommendations_confidence': handoff_state.recommendations_confidence,
            'session_metadata': handoff_state.session_metadata
        }
        
        with open(filename, 'w') as f:
            json.dump(state_dict, f, indent=2, default=str)
        
        print(f"Handoff state saved to: {filename}")


class RitualizedAgent:
    """
    An agent that incorporates shutdown rituals into its operation
    """
    
    def __init__(self):
        self.ritual_manager = ShutdownRitualManager()
        self.active = True
        self.task_queue = []
        self.current_task = None
    
    def work_on_task(self, task_description: str, simulate_completion: bool = True):
        """Work on a task with proper tracking"""
        print(f"Starting task: {task_description}")
        self.ritual_manager.mark_task_in_progress(task_description)
        self.current_task = task_description
        
        if simulate_completion:
            # Simulate some work being done
            time.sleep(0.5)  # Simulate work time
            self.ritual_manager.add_work_completed(
                task_description, 
                f"Achieved initial milestone on {task_description}"
            )
            self.ritual_manager.mark_task_in_progress(task_description)  # Remove from in-progress
            print(f"Completed task: {task_description}")
    
    def encounter_uncertainty(self, question: str, confidence: float = 0.3):
        """Handle encountering an uncertainty"""
        print(f"Encountered uncertainty: {question} (confidence: {confidence})")
        self.ritual_manager.add_uncertainty(question, confidence)
    
    def block_task(self, task: str, reason: str):
        """Block a task due to some issue"""
        print(f"Blocking task: {task} (reason: {reason})")
        self.ritual_manager.mark_task_blocked(task, reason)
    
    def update_progress(self, metric: str, value: Any):
        """Update progress metrics"""
        self.ritual_manager.update_metric(metric, value)
    
    def shutdown_and_handoff(self, context_snapshot: Optional[Dict] = None):
        """Perform shutdown ritual and hand off to human"""
        if not self.active:
            print("Agent already shut down")
            return None
        
        print("\nInitiating shutdown ritual...")
        handoff_state = self.ritual_manager.execute_shutdown_ritual(context_snapshot)
        
        # Optionally save the state
        self.ritual_manager.save_handoff_state(handoff_state)
        
        self.active = False
        return handoff_state
    
    def register_shutdown_procedure(self, procedure: Callable[[], None]):
        """Register a procedure to run during shutdown"""
        self.ritual_manager.register_shutdown_callback(procedure)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python shutdown_handoff_rituals.py <command>")
        print("Commands: demo, interactive")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'demo':
        # Run a demonstration of the shutdown ritual system
        agent = RitualizedAgent()
        
        print("Starting agent session...")
        
        # Simulate some work
        agent.work_on_task("Implement user authentication system")
        agent.work_on_task("Design database schema for user data")
        agent.encounter_uncertainty("What are the specific compliance requirements for user data?")
        agent.block_task("Deploy to production", "Waiting for security review")
        agent.work_on_task("Create unit tests for authentication")
        agent.update_progress("tasks_completed", len(agent.ritual_manager.tasks_completed))
        
        # Perform shutdown ritual
        context_snapshot = {
            "current_files_open": ["/src/auth.py", "/docs/api.md"],
            "pending_reviews": ["security_team", "qa_team"],
            "next_meeting": "2025-01-30 10:00 AM"
        }
        
        handoff_state = agent.shutdown_and_handoff(context_snapshot)
        
        print(f"Shutdown complete. Handoff state created at {datetime.fromtimestamp(handoff_state.timestamp)}")
    
    elif command == 'interactive':
        print("Interactive mode would allow real-time task tracking")
        print("This would typically connect to a live agent system")


if __name__ == "__main__":
    print("Deliberate Shutdown and Handoff Rituals System")
    print("=" * 60)
    
    # Demonstrate the system with a realistic scenario
    agent = RitualizedAgent()
    
    print("🤖 Starting AI agent session...")
    print("Working on implementing a complex feature with multiple dependencies...\n")
    
    # Simulate a realistic work session
    agent.work_on_task("Research OAuth 2.0 implementation patterns")
    agent.work_on_task("Design authentication flow diagram") 
    agent.encounter_uncertainty("Should we implement PKCE for mobile apps?", 0.4)
    agent.work_on_task("Set up development environment")
    agent.work_on_task("Implement basic authentication endpoints")
    agent.block_task("Integrate with legacy system", "API documentation incomplete")
    agent.encounter_uncertainty("How should we handle session expiration?", 0.6)
    agent.work_on_task("Write authentication middleware")
    agent.update_progress("code_coverage", "65%")
    agent.update_progress("tests_passed", 12)
    agent.update_progress("tests_failed", 2)
    
    print("\n🔄 Continuing work on remaining tasks...")
    agent.work_on_task("Implement password reset functionality")
    agent.block_task("Connect to identity provider", "Credentials pending from security team")
    agent.encounter_uncertainty("What's the expected load for auth service?", 0.3)
    agent.work_on_task("Add logging and monitoring")
    agent.update_progress("total_lines_of_code", 1247)
    
    # Add a shutdown procedure
    def cleanup_temporary_files():
        print("🧹 Running cleanup: removing temporary files...")
        # In a real system, this would clean up actual temporary files
    
    agent.register_shutdown_procedure(cleanup_temporary_files)
    
    # Create a context snapshot with relevant information
    context_snapshot = {
        "current_branch": "feature/oauth-integration",
        "open_prs": ["#45 - Auth middleware", "#47 - Session management"],
        "dependencies": ["auth-service", "user-db", "legacy-integration"],
        "stakeholders": ["security-team", "backend-team", "product-owner"],
        "deadline": "2025-02-15",
        "current_build_status": "failing - auth tests"
    }
    
    print(f"\n⏰ Session duration: {(time.time() - agent.ritual_manager.session_start_time):.1f} seconds")
    print("Initiating deliberate shutdown ritual...")
    
    # Perform the shutdown ritual
    handoff_state = agent.shutdown_and_handoff(context_snapshot)
    
    print(f"\n✅ Shutdown ritual completed successfully")
    print(f"📊 Session summary saved to: handoff_state_{datetime.fromtimestamp(handoff_state.timestamp).strftime('%Y%m%d_%H%M%S')}.json")
    
    print("\n🎯 Key Benefits of This System:")
    print("  • Clear accountability for completed/remaining work")
    print("  • Explicit identification of uncertainties")
    print("  • Structured handoff to human operators")
    print("  • Prevention of 'progress illusion' in automation")
    print("  • Preservation of context between sessions")
    print("  • Risk factor identification")
    print("  • Actionable next steps for humans")
    
    print(f"\n🔄 System ready for next session when needed")