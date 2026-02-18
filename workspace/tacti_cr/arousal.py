"""Arousal detector for task complexity and compute modulation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple

from .config import COMPLEXITY_KEYWORDS, DEFAULT_CONFIG, ArousalThresholds


class ArousalLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ArousalState:
    level: ArousalLevel
    score: float
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class ComputePlan:
    model_tier: str
    timeout_multiplier: float
    context_budget: int
    allow_paid: bool


def _token_count(text: str) -> int:
    return len([t for t in text.replace("\n", " ").split(" ") if t])


def _complexity_score(task_input: str, extra_signals: Iterable[str] | None = None) -> tuple[float, Tuple[str, ...]]:
    text = (task_input or "").strip()
    if not text:
        return 0.0, ("empty_input",)

    lower = text.lower()
    reasons = []
    score = 0.0

    tokens = _token_count(text)
    if tokens > 40:
        score += 0.12
        reasons.append("token_count>40")
    if tokens > 120:
        score += 0.14
        reasons.append("token_count>120")
    if tokens > 250:
        score += 0.18
        reasons.append("token_count>250")

    lines = text.count("\n") + 1
    if lines > 10:
        score += 0.08
        reasons.append("line_count>10")

    if "```" in text or "traceback" in lower or "stack trace" in lower:
        score += 0.14
        reasons.append("code_or_traceback")

    if any(mark in lower for mark in ("must", "non-negotiable", "constraint", "gate", "fail-closed")):
        score += 0.10
        reasons.append("strict_constraints")

    keyword_hits = sorted({k for k in COMPLEXITY_KEYWORDS if k in lower})
    if keyword_hits:
        score += min(0.32, len(keyword_hits) * 0.05)
        reasons.append(f"complexity_keywords={len(keyword_hits)}")

    if extra_signals:
        sig_hits = [s for s in extra_signals if s and s.lower() in lower]
        if sig_hits:
            score += min(0.20, len(sig_hits) * 0.05)
            reasons.append(f"extra_signals={len(sig_hits)}")

    bounded = min(1.0, max(0.0, round(score, 4)))
    return bounded, tuple(reasons)


def detect_arousal(
    task_input: str,
    *,
    thresholds: ArousalThresholds | None = None,
    extra_signals: Iterable[str] | None = None,
) -> ArousalState:
    cfg = thresholds or DEFAULT_CONFIG.arousal_thresholds
    score, reasons = _complexity_score(task_input, extra_signals=extra_signals)

    if score <= cfg.low_max:
        level = ArousalLevel.LOW
    elif score <= cfg.medium_max:
        level = ArousalLevel.MEDIUM
    else:
        level = ArousalLevel.HIGH

    return ArousalState(level=level, score=score, reasons=reasons)


def get_compute_allocation(arousal_state: ArousalState) -> ComputePlan:
    plan = DEFAULT_CONFIG.compute_plans[arousal_state.level.value]
    return ComputePlan(
        model_tier=plan.model_tier,
        timeout_multiplier=plan.timeout_multiplier,
        context_budget=plan.context_budget,
        allow_paid=plan.allow_paid,
    )


def recommend_tier(task_input: str) -> str:
    """Convenience helper for routing code paths."""
    state = detect_arousal(task_input)
    return get_compute_allocation(state).model_tier
