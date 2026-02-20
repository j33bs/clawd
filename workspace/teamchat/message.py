from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


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


def canonical_message_hash(message: dict[str, Any]) -> str:
    payload = {
        "ts": str((message or {}).get("ts", "")),
        "role": str((message or {}).get("role", "")),
        "content": str((message or {}).get("content", "")),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["agent_role", "canonical_message_hash", "make_message", "utc_now"]
