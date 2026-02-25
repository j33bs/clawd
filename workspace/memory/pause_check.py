#!/usr/bin/env python3
"""Deterministic, lightweight pause gate heuristics for pre-response checks."""

from __future__ import annotations

import os
import re
from typing import Any

FILLER_PHRASES = (
    "great question",
    "happy to help",
    "let's dive in",
    "in summary",
    "to be honest",
    "as an ai",
    "it depends",
    "generally speaking",
)

AMBIGUOUS_USER_TEXT = {
    "ok",
    "k",
    "hmm",
    "huh",
    "maybe",
    "sure",
    "yes",
    "no",
    "why",
    "what",
    "help",
}



def _clamp(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return round(v, 3)



def _count_pattern(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))



def _enabled(context: dict[str, Any]) -> bool:
    if context.get("enabled") is not None:
        return bool(context.get("enabled"))
    return str(os.getenv("OPENCLAW_PAUSE_CHECK", "0")).strip().lower() in {"1", "true", "yes", "on"}



def pause_check(
    user_text: str,
    assistant_draft: str,
    context: dict[str, Any] | None = None,
    *,
    mode: str = "default",
) -> dict[str, Any]:
    """Return structured pause-gate decision.

    Deterministic in all modes; `context["test_mode"]` avoids any ambient state
    dependence beyond explicit args + OPENCLAW_PAUSE_CHECK (or context.enabled).
    """

    ctx = dict(context or {})
    test_mode = bool(ctx.get("test_mode"))
    enabled = _enabled(ctx)

    user = (user_text or "").strip()
    draft = (assistant_draft or "").strip()
    draft_lower = draft.lower()
    user_lower = user.lower()

    draft_words = re.findall(r"\b[\w'/-]+\b", draft_lower)
    user_words = re.findall(r"\b[\w'/-]+\b", user_lower)

    filler_hits = sum(1 for phrase in FILLER_PHRASES if phrase in draft_lower)
    concrete_hits = 0
    concrete_hits += _count_pattern(r"\b(workspace/|/\w|\.py\b|\.md\b|\.json\b)", draft)
    concrete_hits += _count_pattern(r"\b(pytest|python3|git|npm|bash|openclaw)\b", draft)
    concrete_hits += _count_pattern(r"\b(step|diff|test|flag|path|command)s?\b", draft)
    concrete_hits += _count_pattern(r"https?://", draft)
    concrete_hits += _count_pattern(r"\b\d+(?:\.\d+)?%\b", draft)

    verbosity = len(draft_words)
    user_ambiguous = len(user_words) <= 1 or user_lower in AMBIGUOUS_USER_TEXT

    fills_space = 0.0
    if verbosity >= 80:
        fills_space += 0.35
    elif verbosity >= 40:
        fills_space += 0.2
    fills_space += min(0.45, 0.12 * filler_hits)
    if concrete_hits == 0 and verbosity >= 30:
        fills_space += 0.2

    value_add = 0.0
    if concrete_hits > 0:
        value_add += min(0.75, 0.12 * concrete_hits)
    if verbosity <= 18 and draft:
        value_add += 0.1
    if any(tok in draft_lower for tok in ("because", "therefore", "i changed", "i found")):
        value_add += 0.1

    silence_ok = 0.0
    if user_ambiguous and verbosity >= 40:
        silence_ok += 0.5
    if fills_space >= 0.55 and value_add <= 0.35:
        silence_ok += 0.35
    if not draft:
        silence_ok += 0.6

    fills_space = _clamp(fills_space)
    value_add = _clamp(value_add)
    silence_ok = _clamp(silence_ok)

    decision = "proceed"
    rationale = "pause check disabled"
    felt_sense: str | None = None

    if enabled:
        if silence_ok >= 0.65 and value_add <= 0.45 and fills_space >= 0.45:
            decision = "silence"
            rationale = "draft appears verbose/low-specificity for user signal"
            felt_sense = "hold"
        else:
            rationale = "draft adds concrete value"
            felt_sense = "go"

    if test_mode and not enabled:
        # Explicitly stable rationale when disabled in tests.
        rationale = "pause check disabled"

    return {
        "enabled": enabled,
        "decision": decision,
        "rationale": rationale,
        "signals": {
            "fills_space": fills_space,
            "value_add": value_add,
            "silence_ok": silence_ok,
        },
        "felt_sense": felt_sense,
        "mode": mode,
    }
