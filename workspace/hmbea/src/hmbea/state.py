from __future__ import annotations

from typing import TypedDict

from .schemas import CandidateOutput, EvidenceItem, NormalizedTask, TraceRecord, ValidationResult


class AgentState(TypedDict, total=False):
    raw_request: str
    task: NormalizedTask
    selected_role: str
    selected_model: str
    evidence_items: list[EvidenceItem]
    candidate: CandidateOutput
    validation: ValidationResult
    retries: int
    escalate: bool
    final_answer: str
    trace: list[TraceRecord]
