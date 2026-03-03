"""Task 6 composition-root seam for an Active Inference agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .efe_calculator import evaluate


@dataclass
class ActiveInferenceAgent:
    """Minimal contract-first agent shell."""

    beliefs: dict[str, Any] = field(default_factory=dict)
    model: dict[str, Any] = field(default_factory=dict)

    def step(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        """
        Produce the next action from a single observation.

        TODO: replace heuristic policy extraction with proper generative model updates.
        """
        self.beliefs["last_observation"] = dict(observation)
        policies = observation.get("candidate_policies", [])
        if not isinstance(policies, list) or not policies:
            return {"type": "noop", "reason": "no_candidate_policies"}
        ranked = evaluate(policies=policies, beliefs=self.beliefs, model=self.model)
        return {"type": "policy", "policy": ranked[0]["policy"], "score": ranked[0]["score"]}

