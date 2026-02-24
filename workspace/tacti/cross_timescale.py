"""Cross-timescale controller with reflex, deliberative, and meta layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .arousal import detect_arousal, ArousalLevel


@dataclass(frozen=True)
class ReflexDecision:
    action: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class DeliberativeDecision:
    plan_steps: List[str]
    confidence: float
    reason: str


@dataclass(frozen=True)
class MetaDecision:
    selected_layer: str
    reason: str
    requires_review: bool


@dataclass(frozen=True)
class CrossTimescaleResult:
    meta: MetaDecision
    reflex: ReflexDecision
    deliberative: DeliberativeDecision


class CrossTimescaleController:
    def reflex_layer(self, task_input: str) -> ReflexDecision:
        text = (task_input or "").strip()
        tokens = len(text.split())
        if not text:
            return ReflexDecision("noop", 0.95, "empty_input")
        if tokens <= 20 and "?" in text:
            return ReflexDecision("quick_answer", 0.8, "short_question")
        if tokens <= 40:
            return ReflexDecision("fast_path", 0.65, "low_token_task")
        return ReflexDecision("defer", 0.4, "needs_deliberation")

    def deliberative_layer(self, task_input: str) -> DeliberativeDecision:
        text = (task_input or "").strip()
        arousal = detect_arousal(text)
        steps = [
            "collect_context",
            "evaluate_constraints",
            "choose_execution_plan",
            "verify_outcome",
        ]
        if arousal.level == ArousalLevel.HIGH:
            steps.insert(2, "run_risk_review")
            return DeliberativeDecision(steps, 0.85, "high_complexity")
        if arousal.level == ArousalLevel.MEDIUM:
            return DeliberativeDecision(steps, 0.75, "medium_complexity")
        return DeliberativeDecision(steps[:3], 0.6, "low_complexity")

    def meta_controller(self, task_input: str, *, recent_failures: int = 0) -> MetaDecision:
        reflex = self.reflex_layer(task_input)
        arousal = detect_arousal(task_input)

        if recent_failures >= 2:
            return MetaDecision("deliberative", "failure_recovery_mode", True)
        if arousal.level == ArousalLevel.HIGH:
            return MetaDecision("deliberative", "high_arousal_complexity", True)
        if reflex.action in {"quick_answer", "fast_path"} and reflex.confidence >= 0.65:
            return MetaDecision("reflex", "high_reflex_confidence", False)
        return MetaDecision("deliberative", "default_safe_path", False)

    def process(self, task_input: str, *, recent_failures: int = 0) -> CrossTimescaleResult:
        reflex = self.reflex_layer(task_input)
        deliberative = self.deliberative_layer(task_input)
        meta = self.meta_controller(task_input, recent_failures=recent_failures)
        return CrossTimescaleResult(meta=meta, reflex=reflex, deliberative=deliberative)
