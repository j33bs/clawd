from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

MESSAGE_HASH_VERSION_V2 = "teamchat-msg-sha256-v2"
MESSAGE_HASH_VERSION_LEGACY = "teamchat-msg-sha256-legacy"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def agent_role(name: str) -> str:
    return f"agent:{str(name).strip()}"


def make_message(
    *,
    role: str,
    content: str,
    ts: str | None = None,
    route: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ts": str(ts or utc_now()),
        "role": str(role),
        "content": str(content),
    }
    if isinstance(route, dict) and route:
        row["route"] = dict(route)
    if isinstance(meta, dict) and meta:
        row["meta"] = dict(meta)
    return row


def _route_minimal(route: dict[str, Any] | None) -> dict[str, Any]:
    row = dict(route or {})
    out = {
        "provider": row.get("provider"),
        "model": row.get("model"),
        "reason_code": row.get("reason_code"),
        "attempts": row.get("attempts"),
    }
    return {k: v for k, v in out.items() if v is not None}


def canonical_message_payload(message: dict[str, Any], *, session_id: str | None = None, turn: int | None = None) -> dict[str, Any]:
    meta = dict((message or {}).get("meta", {}) or {})
    route = dict((message or {}).get("route", {}) or {})
    chosen_session_id = str(session_id if session_id is not None else meta.get("session_id", "")).strip()
    raw_turn = turn if turn is not None else meta.get("turn")
    try:
        chosen_turn = int(raw_turn)
    except Exception:
        chosen_turn = 0
    return {
        "session_id": chosen_session_id,
        "turn": int(chosen_turn),
        "role": str((message or {}).get("role", "")),
        "content": str((message or {}).get("content", "")),
        "route_minimal": _route_minimal(route),
        "ts": str((message or {}).get("ts", "")),
    }


def canonical_message_hash_v2(message: dict[str, Any], *, session_id: str | None = None, turn: int | None = None) -> str:
    payload = canonical_message_payload(message, session_id=session_id, turn=turn)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def legacy_message_hash(message: dict[str, Any]) -> str:
    payload = {
        "ts": str((message or {}).get("ts", "")),
        "role": str((message or {}).get("role", "")),
        "content": str((message or {}).get("content", "")),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_message_hash(message: dict[str, Any]) -> str:
    """Backward-compatible alias for legacy hash consumers."""
    return legacy_message_hash(message)


__all__ = [
    "MESSAGE_HASH_VERSION_LEGACY",
    "MESSAGE_HASH_VERSION_V2",
    "agent_role",
    "canonical_message_hash",
    "canonical_message_hash_v2",
    "canonical_message_payload",
    "legacy_message_hash",
    "make_message",
    "utc_now",
]
