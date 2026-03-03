"""Deterministic low-frequency maintenance scheduler."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Set


PHASE_GROUPS = {
    0: {"collapse_detect", "collapse_repair"},
    1: {"dream_consolidation", "knowledge_graph"},
    2: {"peer_graph_updates"},
}
PHASE_LABELS = {
    0: "collapse_maintenance",
    1: "memory_maintenance",
    2: "peer_maintenance",
}


def oscillatory_attention_enabled() -> bool:
    value = str(
        os.environ.get(
            "OPENCLAW_OSCILLATORY_ATTENTION",
            os.environ.get("OPENCLAW_OSCILLATORY_GATING", "0"),
        )
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


@dataclass
class PhaseScheduler:
    phase_len: int = 1

    def phase_for_step(self, step: int, arousal: float | None = None) -> int:
        span = max(1, int(self.phase_len))
        base_phase = (max(0, int(step)) // span) % len(PHASE_GROUPS)
        if arousal is None:
            return base_phase
        if float(arousal) >= 0.8:
            return (base_phase + 1) % len(PHASE_GROUPS)
        return base_phase

    def active_subsystems(self, step: int, arousal: float | None = None) -> Set[str]:
        if not oscillatory_attention_enabled():
            return set().union(*PHASE_GROUPS.values())
        return set(PHASE_GROUPS[self.phase_for_step(step, arousal=arousal)])

    def should_run(self, subsystem_name: str, step: int, arousal: float | None = None) -> bool:
        if not oscillatory_attention_enabled():
            return True
        return str(subsystem_name) in self.active_subsystems(step, arousal=arousal)


@dataclass
class OscillatoryGate:
    phase: int = 0
    phase_len: int = 1

    def tick(self) -> Dict[str, object]:
        scheduler = PhaseScheduler(phase_len=self.phase_len)
        idx = scheduler.phase_for_step(self.phase)
        payload = {
            "enabled": oscillatory_attention_enabled(),
            "phase": idx,
            "active_groups": [PHASE_LABELS[idx]],
        }
        self.phase += 1
        return payload

def select_maintenance_groups(phase: int) -> List[str]:
    scheduler = PhaseScheduler(phase_len=1)
    return sorted(scheduler.active_subsystems(int(phase)))


oscillatory_gating_enabled = oscillatory_attention_enabled


__all__ = [
    "PhaseScheduler",
    "OscillatoryGate",
    "select_maintenance_groups",
    "oscillatory_attention_enabled",
    "oscillatory_gating_enabled",
]
