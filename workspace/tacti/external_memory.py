"""Append-only external memory event store (phase 1)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "workspace" / "artifacts" / "external_memory"
DEFAULT_EVENTS_FILE = DEFAULT_ARTIFACT_ROOT / "events.jsonl"
BACKEND = "jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    value = (proc.stdout or "").strip()
    return value or None


def _events_file_path() -> Path:
    configured = os.environ.get("OPENCLAW_EXTERNAL_MEMORY_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_EVENTS_FILE


def _parse_ts(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def append_event(event_type: str, payload: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")
    if not isinstance(payload, dict):
        raise TypeError("payload must be an object (dict)")
    if meta is not None and not isinstance(meta, dict):
        raise TypeError("meta must be an object (dict)")

    payload_copy = dict(payload)
    meta_copy = dict(meta or {})
    run_id = str(meta_copy.get("run_id") or uuid4())
    event_id = str(uuid4())
    event_meta = {
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "git_sha": _get_git_sha(),
    }
    event_meta.update(meta_copy)

    record = {
        "event_id": event_id,
        "ts_utc": _utc_now_iso(),
        "event_type": event_type.strip(),
        "run_id": run_id,
        "payload": payload_copy,
        "meta": event_meta,
    }

    path = _events_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return event_id


def read_events(
    limit: int | None = None,
    since_ts_utc: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    path = _events_file_path()
    if not path.exists():
        return []

    since_dt = _parse_ts(since_ts_utc) if since_ts_utc else None
    want_event_type = event_type.strip() if isinstance(event_type, str) and event_type.strip() else None
    out: list[dict[str, Any]] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if want_event_type and str(item.get("event_type", "")) != want_event_type:
            continue
        if since_dt is not None:
            item_dt = _parse_ts(str(item.get("ts_utc", "")))
            if item_dt is None or item_dt < since_dt:
                continue
        out.append(item)

    if isinstance(limit, int) and limit >= 0:
        out = out[-limit:]
    return out


def healthcheck() -> dict[str, Any]:
    path = _events_file_path()
    payload: dict[str, Any] = {
        "ok": path.exists() and path.is_file(),
        "path": str(path),
        "backend": BACKEND,
    }
    events = read_events(limit=1)
    if events:
        payload["last_event_ts"] = events[-1].get("ts_utc")
    return payload

