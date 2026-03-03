#!/usr/bin/env python3
"""Golden event envelope helper for health/gate events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_ID = "openclaw.event_envelope.v1"
FORBIDDEN_KEYS = {
    "prompt",
    "text",
    "body",
    "document_body",
    "documentbody",
    "messages",
    "content",
    "raw_content",
    "raw",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_l = str(key).strip().lower()
            if key_l in FORBIDDEN_KEYS:
                continue
            out[str(key)] = _sanitize(item)
        return out
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def contains_forbidden_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() in FORBIDDEN_KEYS:
                return True
            if contains_forbidden_keys(item):
                return True
    elif isinstance(value, list):
        for item in value:
            if contains_forbidden_keys(item):
                return True
    return False


def make_envelope(
    event: str,
    severity: str,
    component: str,
    corr_id: str,
    details: dict[str, Any] | None = None,
    *,
    ts: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "ts": str(ts or utc_now_iso()),
        "event": str(event),
        "severity": str(severity).upper(),
        "component": str(component),
        "corr_id": str(corr_id or ""),
        "details": _sanitize(details or {}),
    }


def append_envelope(path: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    target = Path(path).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        return {"ok": True, "path": str(target)}
    except Exception as exc:
        return {"ok": False, "path": str(target), "error": f"{type(exc).__name__}:{exc}"}
