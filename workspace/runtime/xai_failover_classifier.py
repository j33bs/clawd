#!/usr/bin/env python3
"""Classifier for xAI billing/quota exhaustion failover eligibility."""

from __future__ import annotations

from typing import Iterable

_BILLING_TERMS: tuple[str, ...] = (
    "insufficient credits",
    "payment required",
    "quota exceeded",
    "exceeded your quota",
    "billing",
)

_RATE_LIMIT_TERMS: tuple[str, ...] = (
    "insufficient",
    "quota",
    "rate limit",
    "exceeded",
    "credits",
    "credit",
    "billing",
)

_AUTH_TERMS: tuple[str, ...] = (
    "billing",
    "payment",
    "credits",
    "quota",
    "insufficient",
    "account",
)


def sanitize_body_text(body_text: str, max_len: int = 240) -> str:
    """Return normalized, bounded text for safe matching/logging."""
    text = " ".join((body_text or "").split())
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def is_xai_billing_or_quota_exhausted(status: int, body_text: str) -> bool:
    """Return True when failure signals indicate failover-worthy xAI depletion."""
    clean = sanitize_body_text(body_text).lower()
    try:
        sc = int(status)
    except Exception:
        sc = 0

    if sc == 402:
        return True

    if sc == 429 and _contains_any(clean, _RATE_LIMIT_TERMS):
        return True

    if sc in (401, 403) and _contains_any(clean, _AUTH_TERMS):
        return True

    return _contains_any(clean, _BILLING_TERMS)


__all__ = ["is_xai_billing_or_quota_exhausted", "sanitize_body_text"]
