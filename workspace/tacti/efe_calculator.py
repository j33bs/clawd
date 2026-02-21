"""Task 1 interface seam for Expected Free Energy ranking."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def evaluate(
    policies: Sequence[Mapping[str, Any]],
    beliefs: Mapping[str, Any],
    model: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Rank policies by a minimal EFE-like score.

    TODO: replace with full pragmatic/epistemic decomposition once model contracts settle.
    """
    _ = beliefs
    curiosity = float((model or {}).get("curiosity_coeff", 1.0))
    ranked: list[dict[str, Any]] = []
    for idx, policy in enumerate(policies):
        pragmatic = float(policy.get("pragmatic_value", 0.0))
        epistemic = float(policy.get("epistemic_value", 0.0))
        score = pragmatic + (curiosity * epistemic)
        ranked.append(
            {
                "policy": dict(policy),
                "index": idx,
                "pragmatic_value": pragmatic,
                "epistemic_value": epistemic,
                "score": score,
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked

