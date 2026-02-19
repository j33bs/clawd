"""Collapse detection for repeated failure patterns."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Deque, List

from .config import DEFAULT_CONFIG
from .hivemind_bridge import hivemind_query


@dataclass(frozen=True)
class HealthState:
    status: str
    confidence: float
    warnings: List[str]
    recommended_actions: List[str]


class CollapseDetector:
    def __init__(
        self,
        window_size: int = DEFAULT_CONFIG.collapse.window_size,
        *,
        agent_scope: str = "main",
        use_hivemind: bool = True,
    ):
        self._events: Deque[str] = deque(maxlen=window_size)
        self._agent_scope = agent_scope
        self._use_hivemind = use_hivemind

    def retrieve_similar_failures(self, topic: str = "all models failed timeout error", limit: int = 3) -> List[str]:
        if not self._use_hivemind:
            return []
        rows = hivemind_query(topic, agent=self._agent_scope, limit=limit)
        return [r.content for r in rows if r.content]

    def record_event(self, event: str) -> None:
        self._events.append((event or "").lower())

    def detect_collapse_precursors(self) -> List[str]:
        warnings = []
        errors = sum(1 for e in self._events if any(k in e for k in ("error", "timeout", "abort", "failed")))
        retries = sum(1 for e in self._events if "retry" in e)
        if errors >= DEFAULT_CONFIG.collapse.degraded_threshold:
            warnings.append("repeated_failures")
        if retries >= 3:
            warnings.append("retry_loop")
        if self._events and list(self._events)[-1].count("all models failed"):
            warnings.append("provider_exhaustion")
        return warnings

    def check_health(self) -> HealthState:
        warnings = self.detect_collapse_precursors()
        errors = sum(1 for e in self._events if any(k in e for k in ("error", "timeout", "abort", "failed")))
        historical = self.retrieve_similar_failures() if errors > 0 else []
        if historical:
            warnings = warnings + ["historical_incidents_found"]

        if errors >= DEFAULT_CONFIG.collapse.collapse_threshold:
            return HealthState(
                status="collapse",
                confidence=0.9,
                warnings=warnings,
                recommended_actions=["trip_circuit_breaker", "switch_to_safe_profile", "operator_review", "review_hivemind_incidents"],
            )
        if errors >= DEFAULT_CONFIG.collapse.degraded_threshold:
            return HealthState(
                status="degraded",
                confidence=0.75,
                warnings=warnings,
                recommended_actions=["reduce_parallelism", "increase_backoff", "route_to_stable_provider", "review_hivemind_incidents"],
            )
        return HealthState(
            status="healthy",
            confidence=0.95,
            warnings=warnings,
            recommended_actions=[],
        )


def emit_recommendation(action: str, detail: dict | None = None, *, repo_root: Path | None = None) -> dict:
    """Append advisory recommendation for collapse subsystem consumers."""
    root = Path(repo_root or Path(__file__).resolve().parents[2])
    out = root / "workspace" / "state" / "tacti_cr" / "collapse_recommendations.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": str(action),
        "detail": detail or {},
        "advisory": True,
    }
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")
    return {"ok": True, "path": str(out), "row": row}
