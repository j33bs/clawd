from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("workspace/state_runtime/memory/arousal_state.json")


def _resolve_path(repo_root: Path | str, state_path: Path | None = None) -> Path:
    root = Path(repo_root)
    target = Path(state_path) if state_path is not None else DEFAULT_STATE_PATH
    return target if target.is_absolute() else (root / target)


def _default_state() -> dict[str, Any]:
    return {"schema": 1, "updated_at": "", "sessions": {}}


def load_state(*, repo_root: Path | str, state_path: Path | None = None) -> dict[str, Any]:
    path = _resolve_path(repo_root, state_path=state_path)
    if not path.exists():
        return _default_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()
    if not isinstance(payload, dict):
        return _default_state()
    merged = _default_state()
    merged.update(payload)
    return merged


def save_state(state: dict[str, Any], *, repo_root: Path | str, state_path: Path | None = None) -> Path:
    path = _resolve_path(repo_root, state_path=state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def _tone_to_energy(tone: Any) -> float:
    text = str(tone or "").strip().lower()
    if text in {"high", "urgent", "stressed", "excited"}:
        return 0.85
    if text in {"low", "calm", "flat"}:
        return 0.30
    return 0.50


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def update_from_event(event: dict[str, Any], *, repo_root: Path | str, state_path: Path | None = None) -> dict[str, Any]:
    state = load_state(repo_root=repo_root, state_path=state_path)
    session_id = str(event.get("session_id") or "unknown")
    ts_utc = str(event.get("ts_utc") or event.get("ts") or "")
    role = str(event.get("role") or "unknown")
    tone = str(event.get("tone") or "unlabeled")
    energy = _tone_to_energy(tone)
    sessions = state.setdefault("sessions", {})
    session_state = sessions.setdefault(
        session_id,
        {
            "user_events": 0,
            "assistant_events": 0,
            "last_role": "",
            "last_tone": "unlabeled",
            "last_content_hash": "",
            "arousal": 0.50,
            "temporal_embedding": [0.50, 0.50, 0.50],
            "updated_at": "",
        },
    )
    if role == "user":
        session_state["user_events"] = int(session_state.get("user_events", 0)) + 1
        role_delta = 0.06
    elif role.startswith("agent:") or role == "assistant":
        session_state["assistant_events"] = int(session_state.get("assistant_events", 0)) + 1
        role_delta = -0.02
    else:
        role_delta = 0.0
    baseline = float(session_state.get("arousal", 0.50))
    next_value = _clamp(baseline + role_delta + (energy - 0.5) * 0.10, 0.0, 1.0)
    vector = list(session_state.get("temporal_embedding", [0.50, 0.50, 0.50]))
    while len(vector) < 3:
        vector.append(0.50)
    session_state["temporal_embedding"] = [round(next_value, 4), round(float(vector[0]), 4), round(float(vector[1]), 4)]
    session_state["arousal"] = round(next_value, 4)
    session_state["last_role"] = role
    session_state["last_tone"] = tone
    session_state["last_content_hash"] = str(event.get("content_hash") or "")
    session_state["updated_at"] = ts_utc
    state["updated_at"] = ts_utc
    path = save_state(state, repo_root=repo_root, state_path=state_path)
    return {"ok": True, "path": str(path), "session": session_id, "arousal": session_state["arousal"]}


__all__ = ["DEFAULT_STATE_PATH", "load_state", "save_state", "update_from_event"]
