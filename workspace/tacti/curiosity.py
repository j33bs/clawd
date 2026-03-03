"""Task 8 interface seam for epistemic value scoring."""

from __future__ import annotations

from typing import Any, Mapping


def epistemic_value(state: Mapping[str, Any], action: Mapping[str, Any]) -> float:
    """
    Return a minimal epistemic value estimate.

    TODO: upgrade to uncertainty-reduction objective once state model is finalized.
    """
    _ = state
    if "epistemic_value" in action:
        return float(action.get("epistemic_value", 0.0))
    return float(action.get("uncertainty_delta", 0.0))

