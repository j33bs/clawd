from __future__ import annotations

import re
from typing import Iterable


_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(str(text).lower()) if len(t) >= 3]


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def compute_inquiry_momentum(
    questions: Iterable[str],
    *,
    significance_values: Iterable[float] | None = None,
) -> dict[str, float]:
    """
    INV-005 inquiry momentum proxy.
    Deterministic, lightweight, and bounded to [0, 1].
    """
    q_list = [str(q).strip() for q in questions if str(q).strip()]
    sig_values = [float(x) for x in (significance_values or [])]
    sig = sum(sig_values) / len(sig_values) if sig_values else (1.0 if q_list else 0.0)
    question_count_score = min(1.0, len(q_list) / 5.0)

    vocab = set()
    total_tokens = 0
    for q in q_list:
        toks = _tokens(q)
        total_tokens += len(toks)
        vocab.update(toks)
    diversity = (len(vocab) / max(1, total_tokens)) if total_tokens else 0.0

    score = _clamp01((0.5 * _clamp01(sig)) + (0.3 * question_count_score) + (0.2 * _clamp01(diversity)))
    return {
        "score": round(score, 6),
        "avg_significance": round(_clamp01(sig), 6),
        "question_count_score": round(question_count_score, 6),
        "token_diversity": round(_clamp01(diversity), 6),
    }

