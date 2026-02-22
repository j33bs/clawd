"""Per-agent behavioral mirror state (local-only)."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import is_enabled
from .events import emit


@dataclass
class MirrorMetrics:
    escalation_rate: float
    topic_avoidance_frequency: float
    repair_triggers: int
    p50_latency_ms: float


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_path(agent: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root or Path(__file__).resolve().parents[2])
    return root / "workspace" / "state" / "mirror" / f"{agent}.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "agent": path.stem,
            "events": 0,
            "escalations": 0,
            "avoid_topics": 0,
            "repair_triggers": 0,
            "latency_ms": [],
            "updated_at": _utc(),
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {"agent": path.stem, "events": 0, "escalations": 0, "avoid_topics": 0, "repair_triggers": 0, "latency_ms": []}


def update_from_event(agent: str, event: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Any]:
    if not is_enabled("mirror"):
        return {"ok": False, "reason": "mirror_disabled"}
    path = _state_path(agent, repo_root=repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = _load(path)
    state["events"] = int(state.get("events", 0)) + 1

    event_type = str(event.get("event") or "")
    data = event.get("data", {}) if isinstance(event.get("data"), dict) else {}
    if event_type in {"router_escalate", "planner_review"} or data.get("decision") == "revise":
        state["escalations"] = int(state.get("escalations", 0)) + 1
    if "avoid" in str(data.get("reason", "")).lower():
        state["avoid_topics"] = int(state.get("avoid_topics", 0)) + 1
    if "repair" in event_type or "retry" in str(data).lower():
        state["repair_triggers"] = int(state.get("repair_triggers", 0)) + 1
    if "latency_ms" in data:
        lat = state.get("latency_ms", [])
        lat.append(float(data["latency_ms"]))
        state["latency_ms"] = lat[-200:]

    state["updated_at"] = _utc()
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    emit(
        "tacti_cr.mirror.updated",
        {"agent": agent, "event_type": event_type, "events": state.get("events", 0), "path": str(path)},
    )
    return {"ok": True, "path": str(path)}


def behavioral_fingerprint(agent: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    path = _state_path(agent, repo_root=repo_root)
    state = _load(path)
    events = max(1, int(state.get("events", 0)))
    latency = sorted(float(x) for x in state.get("latency_ms", []))
    p50 = latency[len(latency) // 2] if latency else 0.0
    metrics = MirrorMetrics(
        escalation_rate=round(float(state.get("escalations", 0)) / events, 6),
        topic_avoidance_frequency=round(float(state.get("avoid_topics", 0)) / events, 6),
        repair_triggers=int(state.get("repair_triggers", 0)),
        p50_latency_ms=round(float(p50), 3),
    )
    return {
        "agent": agent,
        "metrics": metrics.__dict__,
        "updated_at": state.get("updated_at"),
        "events": state.get("events", 0),
    }


def write_weekly_report(repo_root: Path, week_id: str, agents: list[str]) -> Path:
    out = repo_root / "workspace" / "audit" / f"mirror_self_report_{week_id}.md"
    lines = [f"# Mirror Self Report {week_id}", ""]
    for agent in agents:
        fp = behavioral_fingerprint(agent, repo_root=repo_root)
        lines.append(f"## {agent}")
        for k, v in fp["metrics"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


__all__ = ["update_from_event", "behavioral_fingerprint", "write_weekly_report"]
