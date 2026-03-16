from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    GENERAL = "general"
    CODE = "code"
    RETRIEVAL = "retrieval"
    REASONING = "reasoning"


class Difficulty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NormalizedTask(BaseModel):
    user_request: str
    task_type: TaskType = TaskType.GENERAL
    difficulty: Difficulty = Difficulty.MEDIUM
    requires_tools: bool = False
    destructive_action_possible: bool = False
    acceptance_tests: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    source_id: str
    content: str
    score: float | None = None


class CandidateOutput(BaseModel):
    summary: str
    answer: str
    risks: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ValidationResult(BaseModel):
    schema_valid: bool
    groundedness: float = Field(default=0.0, ge=0.0, le=1.0)
    critic_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tests_passed: bool = False
    reasons: list[str] = Field(default_factory=list)


class TraceRecord(BaseModel):
    node: str
    metadata: dict[str, Any] = Field(default_factory=dict)
