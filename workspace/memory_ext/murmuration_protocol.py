from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BoundedContext:
    max_neighbors: int = 7
    neighbors: List[Dict[str, Any]] = field(default_factory=list)

    def observe(self, perceived_state: Dict[str, Any]) -> None:
        self.neighbors.append(dict(perceived_state or {}))
        self.neighbors = self.neighbors[-self.max_neighbors :]


def apply_local_rule(perceived_state: Dict[str, Any]) -> Dict[str, Any]:
    stress = float(perceived_state.get("stress", 0.0))
    energy = float(perceived_state.get("energy", 0.0))
    harmony = float(perceived_state.get("harmony", 0.0))
    if stress >= 0.7:
        action = "moderate"
    elif harmony >= 0.7:
        action = "align"
    elif energy >= 0.7:
        action = "amplify"
    elif float(perceived_state.get("silence", 0.0)) >= 0.7:
        action = "reach_out"
    else:
        action = "stabilize"
    return {"action": action, "stress": stress, "energy": energy, "harmony": harmony}


def emergent_state(contexts: List[BoundedContext]) -> Dict[str, Any]:
    actions: List[str] = []
    total_energy = 0.0
    count = 0
    for context in contexts:
        for neighbor in context.neighbors:
            rule = apply_local_rule(neighbor)
            actions.append(rule["action"])
            total_energy += float(rule.get("energy", 0.0))
            count += 1
    coherence = 0.0
    direction = "stable"
    if actions:
        top = max(set(actions), key=actions.count)
        coherence = float(actions.count(top)) / float(len(actions))
        direction = top
    avg_energy = total_energy / float(count or 1)
    return {"coherence": coherence, "direction": direction, "energy": avg_energy}


def murmurate(conversation_state: Dict[str, Any]) -> Dict[str, Any]:
    context = BoundedContext()
    context.observe(conversation_state)
    state = emergent_state([context])
    state["local_action"] = apply_local_rule(conversation_state).get("action")
    return state


__all__ = ["BoundedContext", "apply_local_rule", "emergent_state", "murmurate"]
