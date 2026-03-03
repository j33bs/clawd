"""Task 1 interface seam for Expected Free Energy ranking."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def evaluate(
    policies: Sequence[Mapping[str, Any]],
    beliefs: Mapping[str, Any],
    model: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Rank policies by a deterministic lightweight EFE proxy.

    score = utility_weight*expected_utility
            + epistemic_weight*epistemic_value
            - arousal_weight*arousal_penalty
            - collapse_penalty
    """
    beliefs = dict(beliefs or {})
    model = dict(model or {})
    utility_weight = float(model.get("utility_weight", 1.0))
    epistemic_weight = float(model.get("epistemic_weight", model.get("curiosity_coeff", 0.7)))
    arousal_weight = float(model.get("arousal_weight", 0.5))
    collapse_penalty_weight = float(model.get("collapse_penalty_weight", 1.0))
    target_arousal = float(model.get("target_arousal", 0.45))
    current_arousal = float(beliefs.get("arousal", 0.45))
    collapse_mode = bool(beliefs.get("collapse_mode", False) or beliefs.get("suppress_heavy", False))

    ranked: list[dict[str, Any]] = []
    for idx, policy in enumerate(policies):
        expected_utility = float(
            policy.get(
                "expected_utility",
                policy.get("pragmatic_value", 0.0),
            )
        )
        epistemic = float(policy.get("epistemic_value", 0.0))
        complexity = max(0.0, float(policy.get("complexity", 0.5)))
        arousal_excess = max(0.0, current_arousal - target_arousal)
        arousal_penalty = arousal_excess * complexity
        collapse_penalty = collapse_penalty_weight * complexity if collapse_mode and complexity > 0.5 else 0.0
        score = (
            (utility_weight * expected_utility)
            + (epistemic_weight * epistemic)
            - (arousal_weight * arousal_penalty)
            - collapse_penalty
        )
        ranked.append(
            {
                "policy": dict(policy),
                "index": idx,
                "expected_utility": expected_utility,
                "epistemic_value": epistemic,
                "arousal_penalty": arousal_penalty,
                "collapse_penalty": collapse_penalty,
                "score": score,
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked
