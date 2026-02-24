"""Affective valence engine with half-life decay and routing bias signals."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_float, is_enabled
from .events import emit


def _state_path(agent: str, repo_root: Path | None = None) -> Path:
    root = Path(repo_root or Path(__file__).resolve().parents[2])
    return root / "workspace" / "state" / "valence" / f"{agent}.json"


def _now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"valence": 0.0, "updated_at": _now().isoformat()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {"valence": 0.0, "updated_at": _now().isoformat()}


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def current_valence(agent: str, *, repo_root: Path | None = None, now: datetime | None = None) -> float:
    if not is_enabled("valence"):
        return 0.0
    path = _state_path(agent, repo_root=repo_root)
    data = _load(path)
    dt_now = _now(now)
    updated = _now(datetime.fromisoformat(str(data.get("updated_at", dt_now.isoformat())).replace("Z", "+00:00")))
    age_hours = max(0.0, (dt_now - updated).total_seconds() / 3600.0)
    half_life = get_float("valence_half_life_hours", 6.0, clamp=(0.5, 48.0))
    decayed = float(data.get("valence", 0.0)) * math.exp(-math.log(2.0) * age_hours / half_life)
    return max(-1.0, min(1.0, decayed))


def update_valence(agent: str, outcome: dict[str, Any], *, repo_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    if not is_enabled("valence"):
        return {"ok": False, "reason": "valence_disabled", "valence": 0.0}
    dt_now = _now(now)
    value = current_valence(agent, repo_root=repo_root, now=dt_now)
    delta = 0.0
    if outcome.get("success") is True:
        delta += 0.12
    if outcome.get("failed") is True:
        delta -= 0.18
    if outcome.get("budget_overrun") is True:
        delta -= 0.10
    if int(outcome.get("retry_loops", 0)) > 0:
        delta -= 0.05 * int(outcome.get("retry_loops", 0))
    value = max(-1.0, min(1.0, value + delta))
    payload = {"agent": agent, "valence": value, "updated_at": dt_now.isoformat().replace("+00:00", "Z")}
    _save(_state_path(agent, repo_root=repo_root), payload)
    emit("tacti_cr.valence.updated", {"agent": agent, "valence": value, "delta": delta}, now=dt_now)
    return {"ok": True, "valence": value}


def routing_bias(agent: str, *, repo_root: Path | None = None) -> dict[str, Any]:
    value = current_valence(agent, repo_root=repo_root)
    return {
        "valence": value,
        "prefer_local": bool(value < -0.2),
        "tighten_budget": bool(value < -0.35),
        "exploration_bias": bool(value > 0.35),
    }


__all__ = ["current_valence", "update_valence", "routing_bias"]
