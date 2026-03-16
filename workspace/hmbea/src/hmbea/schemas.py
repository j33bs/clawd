"""HMBEA Schemas"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    GENERAL = "general"
    CODE = "code"
    RESEARCH = "research"
    CREATIVE = "creative"


class Difficulty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Role(str, Enum):
    CONTROLLER = "controller"
    CODER = "coder"
    CRITIC = "critic"


class EvidenceItem(BaseModel):
    source_id: str
    content: str
    score: float = 1.0


class NormalizedTask(BaseModel):
    user_request: str
    task_type: TaskType
    difficulty: Difficulty
    requires_tools: bool = False
    destructive_action_possible: bool = False


class CandidateAnswer(BaseModel):
    answer: str
    risks: list[str] = []
    actions: list[str] = []
    evidence_ids: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)


class ValidationResult(BaseModel):
    schema_valid: bool
    groundedness: float = Field(ge=0.0, le=1.0)
    critic_score: float = Field(ge=0.0, le=1.0)
    tests_passed: bool = False
    reasons: list[str] = []


class TraceRecord(BaseModel):
    node: str
    metadata: dict = {}


class AgentState(BaseModel):
    raw_request: str = ""
    task: Optional[NormalizedTask] = None
    evidence_items: list[EvidenceItem] = []
    selected_role: Optional[Role] = None
    selected_model: Optional[str] = None
    candidate: Optional[CandidateAnswer] = None
    validation: Optional[ValidationResult] = None
    final_answer: Optional[str] = None
    escalate: bool = False
    retries: int = 0
    trace: list[TraceRecord] = []
