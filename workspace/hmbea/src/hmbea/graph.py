from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langgraph.graph import END, START, StateGraph

from .clients import OpenAICompatibleClient
from .config import get_settings
from .model_router import ModelRouter
from .schemas import CandidateOutput, Difficulty, EvidenceItem, NormalizedTask, TaskType, TraceRecord
from .state import AgentState
from .validators import DeterministicValidator
from .shadow import get_shadow_system


ROOT = Path(__file__).resolve().parents[4]


def _trace(state: AgentState, node: str, **metadata: Any) -> None:
    state.setdefault("trace", [])
    state["trace"].append(TraceRecord(node=node, metadata=metadata))


class GraphRuntime:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.router = ModelRouter(ROOT / settings.registry_path)
        self.validator = DeterministicValidator()
        self.controller = OpenAICompatibleClient(settings.controller_base_url, settings.controller_model)
        self.specialist = OpenAICompatibleClient(settings.specialist_base_url, settings.specialist_model)
        self.critic = OpenAICompatibleClient(settings.critic_base_url, settings.critic_model)
        with (ROOT / settings.escalation_policy_path).open("r", encoding="utf-8") as f:
            self.escalation = yaml.safe_load(f)
        
        # Shadow system for learning
        self.shadow = get_shadow_system()

    def intake(self, state: AgentState) -> AgentState:
        request = state["raw_request"]
        lower = request.lower()
        task_type = TaskType.CODE if any(k in lower for k in ["code", "repo", "patch", "bug", "refactor"]) else TaskType.GENERAL
        difficulty = Difficulty.HIGH if any(k in lower for k in ["research", "audit", "implement", "harden"]) else Difficulty.MEDIUM
        state["task"] = NormalizedTask(
            user_request=request,
            task_type=task_type,
            difficulty=difficulty,
            requires_tools=task_type == TaskType.CODE,
            destructive_action_possible=False,
            acceptance_tests=[],
        )
        _trace(state, "intake", task_type=state["task"].task_type, difficulty=state["task"].difficulty)
        return state

    def retrieve(self, state: AgentState) -> AgentState:
        task = state["task"]
        evidence = [
            EvidenceItem(source_id="task", content=task.user_request, score=1.0),
        ]
        # TODO: replace with hybrid retrieval + reranking over your local store.
        state["evidence_items"] = evidence
        _trace(state, "retrieve", evidence_count=len(evidence))
        return state

    def route(self, state: AgentState) -> AgentState:
        task = state["task"]
        role = self.router.select_role(task.task_type)
        model = self.router.select_model(role)
        state["selected_role"] = role
        state["selected_model"] = model["name"]
        _trace(state, "route", role=role, model=model["name"])
        return state

    def execute(self, state: AgentState) -> AgentState:
        task = state["task"]
        evidence_block = "\n".join(f"[{e.source_id}] {e.content}" for e in state.get("evidence_items", []))
        system = (
            "You are a local specialist in a hardened orchestration graph. "
            "Return only valid JSON matching the schema. "
            "Use evidence ids exactly as provided. "
            "Be conservative: do not claim unsupported facts."
        )
        user = (
            f"TASK:\n{task.user_request}\n\n"
            f"TASK_TYPE: {task.task_type.value}\n"
            f"DIFFICULTY: {task.difficulty.value}\n\n"
            f"EVIDENCE:\n{evidence_block}\n\n"
            "Produce a concise answer, explicit risks, concrete actions, evidence ids, and a calibrated confidence."
        )
        client = self.specialist if state["selected_role"] in {"coder", "critic"} else self.controller
        response = client.chat_json(system=system, user=user, schema=CandidateOutput)
        state["candidate"] = CandidateOutput.from_response(response)
        
        # Record to shadow system for learning
        self.shadow.record_frontier(
            task=task.user_request,
            task_type=task.task_type.value,
            difficulty=task.difficulty.value,
            output=state["candidate"].answer,
            confidence=state["candidate"].confidence,
        )
        
        _trace(state, "execute", confidence=state["candidate"].confidence)
        return state

    def validate(self, state: AgentState) -> AgentState:
        task = state["task"]
        candidate = state["candidate"]
        validation = self.validator.run(candidate, state.get("evidence_items", []), task.acceptance_tests)
        state["validation"] = validation
        _trace(
            state,
            "validate",
            schema_valid=validation.schema_valid,
            groundedness=validation.groundedness,
            critic_score=validation.critic_score,
            tests_passed=validation.tests_passed,
        )
        return state

    def gate(self, state: AgentState) -> AgentState:
        v = state["validation"]
        accept = (
            v.schema_valid
            and v.tests_passed
            and v.groundedness >= self.escalation["thresholds"]["accept_if"]["groundedness_gte"]
            and v.critic_score >= self.escalation["thresholds"]["accept_if"]["critic_score_gte"]
        )
        retry_lo, retry_hi = self.escalation["thresholds"]["retry_if"]["critic_score_between"]
        retries = state.get("retries", 0)
        if accept:
            state["escalate"] = False
            state["final_answer"] = state["candidate"].answer
            _trace(state, "gate", decision="accept")
            return state
        if retry_lo <= v.critic_score <= retry_hi and retries < self.escalation["thresholds"]["retry_if"]["max_retries"]:
            state["retries"] = retries + 1
            state["escalate"] = False
            _trace(state, "gate", decision="retry", retries=state["retries"])
            return state
        state["escalate"] = True
        state["final_answer"] = (
            "Escalation required. The local path did not meet acceptance thresholds.\n\n"
            f"Reasons: {', '.join(v.reasons) if v.reasons else 'threshold miss'}"
        )
        _trace(state, "gate", decision="escalate")
        return state

    def should_retry(self, state: AgentState) -> str:
        if state.get("escalate"):
            return "finalize"
        if state.get("validation") and not state["final_answer"]:
            return "execute"
        return "finalize"

    def finalize(self, state: AgentState) -> AgentState:
        if not state.get("final_answer"):
            state["final_answer"] = state["candidate"].answer
        _trace(state, "finalize")
        return state

    def build(self):
        graph = StateGraph(AgentState)
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
        graph.add_conditional_edges("gate", self.should_retry, {"execute": "execute", "finalize": "finalize"})
        graph.add_edge("finalize", END)
        return graph.compile()
