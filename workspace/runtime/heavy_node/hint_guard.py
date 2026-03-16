#!/usr/bin/env python3
"""Hint strictness guardrails for /hint endpoint."""

from __future__ import annotations

import re
from typing import List, Tuple

FULL_SOLUTION_PATTERNS = [
    re.compile(r"```", re.IGNORECASE),
    re.compile(r"\bhere'?s\s+the\s+full\s+solution\b", re.IGNORECASE),
    re.compile(r"\bcomplete\s+solution\b", re.IGNORECASE),
    re.compile(r"\bfinal\s+answer\b", re.IGNORECASE),
    re.compile(r"\bdef\s+\w+\(|\bclass\s+\w+\s*[:\(]", re.IGNORECASE),
    re.compile(r"\b#include\b|\bpublic\s+static\s+void\b", re.IGNORECASE),
    re.compile(r"\bstep\s*1\b.*\bstep\s*2\b", re.IGNORECASE | re.DOTALL),
]


def _estimate_tokens(text: str) -> int:
    return max(0, len(str(text or "")) // 4)


def _normalize_lines(text: str) -> List[str]:
    raw = str(text or "").replace("\r", "\n")
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    lines = [line.strip(" -\t") for line in raw.split("\n")]
    lines = [line for line in lines if line]
    if len(lines) == 1:
        # Split by sentences for better hint granularity.
        chunks = [c.strip() for c in re.split(r"(?<=[\.!?])\s+", lines[0]) if c.strip()]
        if len(chunks) > 1:
            return chunks
    return lines


def _is_full_solution(text: str) -> bool:
    lower = str(text or "")
    if _estimate_tokens(lower) > 320:
        return True
    return any(p.search(lower) for p in FULL_SOLUTION_PATTERNS)


def _fallback_hint(problem: str) -> List[str]:
    problem = (problem or "").strip()
    seed = "Identify the single blocking assumption in your current approach."
    if problem:
        seed = f"Restate the goal in one sentence: {problem[:90]}"
    return [
        seed,
        "Try one small check that falsifies your strongest assumption.",
        "Only after that, adjust one variable and retry.",
    ]


def enforce_hint_only(
    text: str,
    *,
    problem: str,
    budget_tokens: int,
    max_lines: int,
) -> Tuple[str, bool]:
    """Return strict short hint text + truncation flag."""
    budget_tokens = max(16, int(budget_tokens or 60))
    max_lines = max(2, min(6, int(max_lines or 6)))

    used_fallback = _is_full_solution(text)
    lines = _fallback_hint(problem) if used_fallback else _normalize_lines(text)

    if len(lines) < 2:
        lines = lines + ["Check one edge case before changing the full plan."]
    if len(lines) > max_lines:
        lines = lines[:max_lines]

    # Token budget by trimming lines from end and clipping last line.
    joined = "\n".join(lines)
    while _estimate_tokens(joined) > budget_tokens and len(lines) > 2:
        lines = lines[:-1]
        joined = "\n".join(lines)

    if _estimate_tokens(joined) > budget_tokens:
        # Final clip preserving at least 2 lines.
        char_budget = budget_tokens * 4
        joined = joined[:char_budget].rstrip()
        lines = _normalize_lines(joined)
        if len(lines) < 2:
            lines = _fallback_hint(problem)[:2]
        joined = "\n".join(lines[:max_lines])

    joined = "\n".join(lines[:max_lines]).strip()
    if joined.count("\n") + 1 < 2:
        joined = f"{joined}\nCheck one assumption before retrying."

    truncated = used_fallback or (joined != str(text or "").strip())
    return joined, truncated
