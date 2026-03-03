from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("workspace/state_runtime/memory/relationship_state.json")


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


def _tone_adjustment(tone: str) -> float:
    label = str(tone or "").strip().lower()
    if label in {"supportive", "warm", "calm", "positive"}:
        return 0.03
    if label in {"hostile", "frustrated", "negative"}:
        return -0.04
    return 0.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def update_from_event(event: dict[str, Any], *, repo_root: Path | str, state_path: Path | None = None) -> dict[str, Any]:
    state = load_state(repo_root=repo_root, state_path=state_path)
    session_id = str(event.get("session_id") or "unknown")
    role = str(event.get("role") or "unknown")
    tone = str(event.get("tone") or "unlabeled")
    ts_utc = str(event.get("ts_utc") or event.get("ts") or "")

    sessions = state.setdefault("sessions", {})
    session_state = sessions.setdefault(
        session_id,
        {
            "user_events": 0,
            "assistant_events": 0,
            "trust_score": 0.50,
            "attunement_index": 0.50,
            "open_count": 0,
            "close_count": 0,
            "unresolved_threads": 0,
            "last_summary_ref": "",
            "last_tone": "unlabeled",
            "last_content_hash": "",
            "updated_at": "",
        },
    )

    if role == "user":
        session_state["user_events"] = int(session_state.get("user_events", 0)) + 1
        trust_delta = 0.01
    elif role.startswith("agent:") or role == "assistant":
        session_state["assistant_events"] = int(session_state.get("assistant_events", 0)) + 1
        trust_delta = 0.005
    else:
        trust_delta = 0.0
    trust = float(session_state.get("trust_score", 0.50))
    attunement = float(session_state.get("attunement_index", 0.50))
    trust = _clamp(trust + trust_delta + _tone_adjustment(tone), 0.0, 1.0)
    balance = min(int(session_state.get("user_events", 0)), int(session_state.get("assistant_events", 0)))
    denominator = max(int(session_state.get("user_events", 0)), int(session_state.get("assistant_events", 0)), 1)
    attunement = _clamp((balance / denominator) * 0.70 + trust * 0.30, 0.0, 1.0)

    session_state["trust_score"] = round(trust, 4)
    session_state["attunement_index"] = round(attunement, 4)
    session_state["last_tone"] = tone
    session_state["last_content_hash"] = str(event.get("content_hash") or "")
    session_state["updated_at"] = ts_utc
    state["updated_at"] = ts_utc
    path = save_state(state, repo_root=repo_root, state_path=state_path)
    return {
        "ok": True,
        "path": str(path),
        "session": session_id,
        "trust_score": session_state["trust_score"],
        "attunement_index": session_state["attunement_index"],
    }


def record_session_open(session_id: str, *, repo_root: Path | str, ts_utc: str, outstanding_threads: int = 0) -> dict[str, Any]:
    state = load_state(repo_root=repo_root)
    sessions = state.setdefault("sessions", {})
    session_state = sessions.setdefault(
        str(session_id),
        {
            "user_events": 0,
            "assistant_events": 0,
            "trust_score": 0.50,
            "attunement_index": 0.50,
            "open_count": 0,
            "close_count": 0,
            "unresolved_threads": 0,
            "last_summary_ref": "",
            "last_tone": "unlabeled",
            "last_content_hash": "",
            "updated_at": "",
        },
    )
    session_state["open_count"] = int(session_state.get("open_count", 0)) + 1
    session_state["unresolved_threads"] = max(0, int(outstanding_threads))
    session_state["updated_at"] = str(ts_utc)
    state["updated_at"] = str(ts_utc)
    path = save_state(state, repo_root=repo_root)
    return {"ok": True, "path": str(path), "session": str(session_id)}


def record_session_close(
    session_id: str,
    *,
    repo_root: Path | str,
    ts_utc: str,
    unresolved_threads: int = 0,
    summary_ref: str = "",
) -> dict[str, Any]:
    state = load_state(repo_root=repo_root)
    sessions = state.setdefault("sessions", {})
    session_state = sessions.setdefault(
        str(session_id),
        {
            "user_events": 0,
            "assistant_events": 0,
            "trust_score": 0.50,
            "attunement_index": 0.50,
            "open_count": 0,
            "close_count": 0,
            "unresolved_threads": 0,
            "last_summary_ref": "",
            "last_tone": "unlabeled",
            "last_content_hash": "",
            "updated_at": "",
        },
    )
    session_state["close_count"] = int(session_state.get("close_count", 0)) + 1
    session_state["unresolved_threads"] = max(0, int(unresolved_threads))
    session_state["last_summary_ref"] = str(summary_ref or "")
    session_state["updated_at"] = str(ts_utc)
    state["updated_at"] = str(ts_utc)
    path = save_state(state, repo_root=repo_root)
    return {"ok": True, "path": str(path), "session": str(session_id)}


__all__ = [
    "DEFAULT_STATE_PATH",
    "load_state",
    "save_state",
    "update_from_event",
    "record_session_open",
    "record_session_close",
]
