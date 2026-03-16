"""HMBEA Graph - Core Orchestration"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langgraph.graph import END, START, StateGraph

from .clients import OpenAICompatibleClient
from .config import get_settings
from .model_router import ModelRouter
from .schemas import (
    AgentState, CandidateAnswer, Difficulty, EvidenceItem, 
    NormalizedTask, Role, TaskType, TraceRecord
)
from .validators import DeterministicValidator


def _trace(state: dict, node: str, **metadata: Any) -> None:
    state.setdefault("trace", [])
    state["trace"].append({"node": node, "metadata": metadata})


class HMBEAGraph:
    """Hierarchical Multi-Being Evolutionary Architecture - Core Runtime"""
    
    def __init__(self, root: Path = None):
        root = root or Path.cwd()
        settings = get_settings()
        self.settings = settings
        self.root = root
        
        # Load configs
        registry_path = root / settings.registry_path
        self.router = ModelRouter(registry_path)
        self.validator = DeterministicValidator()
        
        with open(root / settings.escalation_policy_path) as f:
            self.escalation = yaml.safe_load(f)
        
        # Initialize clients (lazy - connect when needed)
        self._controller = None
        self._specialist = None
        self._critic = None
    
    @property
    def controller(self):
        if self._controller is None:
            self._controller = OpenAICompatibleClient(
                self.settings.controller_base_url,
                self.settings.controller_model
            )
        return self._controller
    
    @property
    def specialist(self):
        if self._specialist is None:
            self._specialist = OpenAICompatibleClient(
                self.settings.specialist_base_url,
                self.settings.specialist_model
            )
        return self._specialist
    
    @property
    def critic(self):
        if self._critic is None:
            self._critic = OpenAICompatibleClient(
                self.settings.critic_base_url,
                self.settings.critic_model
            )
        return self._critic
    
    def intake(self, state: dict) -> dict:
        """Normalize incoming task."""
        request = state.get("raw_request", "")
        lower = request.lower()
        
        # Classify task type
        if any(k in lower for k in ["code", "repo", "patch", "bug", "refactor", "implement"]):
            task_type = TaskType.CODE
        elif any(k in lower for k in ["research", "find", "search"]):
            task_type = TaskType.RESEARCH
        elif any(k in lower for k in ["write", "create", "story", "creative"]):
            task_type = TaskType.CREATIVE
        else:
            task_type = TaskType.GENERAL
        
        # Classify difficulty
        difficulty = Difficulty.HIGH if any(k in lower for k in [
            "research", "audit", "implement", "harden", "design", "architect"
        ]) else Difficulty.MEDIUM
        
        state["task"] = {
            "user_request": request,
            "task_type": task_type.value,
            "difficulty": difficulty.value,
            "requires_tools": task_type == TaskType.CODE,
        }
        
        _trace(state, "intake", task_type=task_type.value, difficulty=difficulty.value)
        return state
    
    def retrieve(self, state: dict) -> dict:
        """Retrieve relevant context."""
        task = state.get("task", {})
        request = task.get("user_request", "")
        
        # Placeholder - would integrate with actual retrieval
        evidence = [
            {"source_id": "task", "content": request, "score": 1.0}
        ]
        state["evidence_items"] = evidence
        _trace(state, "retrieve", evidence_count=len(evidence))
        return state
    
    def route(self, state: dict) -> dict:
        """Route to appropriate role and model."""
        task = state.get("task", {})
        task_type = TaskType(task.get("task_type", "general"))
        
        role = self.router.select_role(task_type)
        model = self.router.select_model(role)
        
        state["selected_role"] = role.value
        state["selected_model"] = model.get("name", "unknown")
        
        _trace(state, "route", role=role.value, model=model["name"])
        return state
    
    def execute(self, state: dict) -> dict:
        """Execute task with selected role."""
        task = state.get("task", {})
        evidence = state.get("evidence_items", [])
        
        evidence_block = "\n".join(f"[{e['source_id']}] {e['content']}" for e in evidence)
        
        system = (
            "You are a local specialist in a hardened orchestration graph. "
            "Return only valid JSON. "
            "Be conservative: do not claim unsupported facts."
        )
        
        user = (
            f"TASK: {task.get('user_request')}\n\n"
            f"TASK_TYPE: {task.get('task_type')}\n"
            f"DIFFICULTY: {task.get('difficulty')}\n\n"
            f"EVIDENCE:\n{evidence_block}\n\n"
            "Produce a concise answer, explicit risks, actions, evidence ids, and confidence."
        )
        
        # Select client based on role
        role = state.get("selected_role")
        if role in ("coder", "critic"):
            client = self.specialist
        else:
            client = self.controller
        
        try:
            response = client.chat_json(system=system, user=user, schema=dict)
            candidate = {
                "answer": response.get("answer", str(response)),
                "risks": response.get("risks", []),
                "actions": response.get("actions", []),
                "evidence_ids": response.get("evidence_ids", []),
                "confidence": response.get("confidence", 0.5),
            }
        except Exception as e:
            candidate = {
                "answer": f"Error: {str(e)}",
                "risks": ["execution error"],
                "actions": [],
                "evidence_ids": [],
                "confidence": 0.0,
            }
        
        state["candidate"] = candidate
        _trace(state, "execute", confidence=candidate["confidence"])
        return state
    
    def validate(self, state: dict) -> dict:
        """Validate candidate output."""
        candidate = state.get("candidate", {})
        evidence = state.get("evidence_items", [])
        
        validation = self.validator.run(
            CandidateAnswer(**candidate),
            [EvidenceItem(**e) for e in evidence],
            []
        )
        
        state["validation"] = {
            "schema_valid": validation.schema_valid,
            "groundedness": validation.groundedness,
            "critic_score": validation.critic_score,
            "tests_passed": validation.tests_passed,
            "reasons": validation.reasons,
        }
        
        _trace(state, "validate", 
               schema_valid=validation.schema_valid,
               groundedness=validation.groundedness,
               critic_score=validation.critic_score)
        return state
    
    def gate(self, state: dict) -> dict:
        """Gate decision - accept/retry/escalate."""
        v = state.get("validation", {})
        thresholds = self.escalation.get("thresholds", {})
        
        accept_if = thresholds.get("accept_if", {})
        retry_if = thresholds.get("retry_if", {})
        
        # Accept?
        accept = (
            v.get("schema_valid", False)
            and v.get("tests_passed", False)
            and v.get("groundedness", 0) >= accept_if.get("groundedness_gte", 0.75)
            and v.get("critic_score", 0) >= accept_if.get("critic_score_gte", 0.80)
        )
        
        if accept:
            state["escalate"] = False
            state["final_answer"] = state.get("candidate", {}).get("answer", "")
            _trace(state, "gate", decision="accept")
            return state
        
        # Retry?
        retry_range = retry_if.get("critic_score_between", [0.55, 0.79])
        retries = state.get("retries", 0)
        max_retries = retry_if.get("max_retries", 1)
        
        if retry_range[0] <= v.get("critic_score", 0) <= retry_range[1] and retries < max_retries:
            state["retries"] = retries + 1
            state["escalate"] = False
            _trace(state, "gate", decision="retry", retries=state["retries"])
            return state
        
        # Escalate
        state["escalate"] = True
        state["final_answer"] = (
            f"Escalation required. Local path did not meet thresholds.\n"
            f"Critic score: {v.get('critic_score', 0):.2f}"
        )
        _trace(state, "gate", decision="escalate")
        return state
    
    def should_retry(self, state: dict) -> str:
        """Determine next step after gate."""
        if state.get("escalate"):
            return "finalize"
        if state.get("validation") and not state.get("final_answer"):
            return "execute"
        return "finalize"
    
    def finalize(self, state: dict) -> dict:
        """Finalize and return result."""
        if not state.get("final_answer"):
            state["final_answer"] = state.get("candidate", {}).get("answer", "")
        _trace(state, "finalize")
        return state
    
    def build_graph(self):
        """Build LangGraph workflow."""
        graph = StateGraph(dict)
        
        graph.add_node("intake", self.intake)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("route", self.route)
        graph.add_node("execute", self.execute)
        graph.add_node("validate", self.validate)
        graph.add_node("gate", self.gate)
        graph.add_node("finalize", self.finalize)
        
        graph.add_edge(START, "intake")
        graph.add_edge("intake", "retrieve")
        graph.add_edge("retrieve", "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", "validate")
        graph.add_edge("validate", "gate")
        graph.add_conditional_edges("gate", self.should_retry, 
                                    {"execute": "execute", "finalize": "finalize"})
        graph.add_edge("finalize", END)
        
        return graph.compile()
    
    def run(self, request: str) -> dict:
        """Run a task through the HMBEA pipeline."""
        graph = self.build_graph()
        initial_state = {"raw_request": request}
        result = graph.invoke(initial_state)
        return result


# Convenience function
def run_task(request: str) -> dict:
    """Run a task through HMBEA."""
    runtime = HMBEAGraph()
    return runtime.run(request)
