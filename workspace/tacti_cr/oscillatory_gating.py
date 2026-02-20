"""Deterministic low-frequency maintenance scheduler."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List


GROUPS = [
    ["memory_maintenance"],
    ["routing_maintenance"],
    ["audit_maintenance"],
    ["immune_maintenance"],
]


def oscillatory_gating_enabled() -> bool:
    value = str(os.environ.get("OPENCLAW_OSCILLATORY_GATING", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


@dataclass
class OscillatoryGate:
    phase: int = 0

    def tick(self) -> Dict[str, object]:
        if not oscillatory_gating_enabled():
            return {"enabled": False, "phase": self.phase, "active_groups": []}
        idx = self.phase % len(GROUPS)
        active = list(GROUPS[idx])
        self.phase += 1
        return {"enabled": True, "phase": idx, "active_groups": active}


def select_maintenance_groups(phase: int) -> List[str]:
    idx = int(phase) % len(GROUPS)
    return list(GROUPS[idx])


__all__ = ["OscillatoryGate", "select_maintenance_groups", "oscillatory_gating_enabled"]
