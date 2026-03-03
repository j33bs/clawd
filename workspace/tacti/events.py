"""Unified TACTI-CR runtime event contract (append-only JSONL)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH = Path("workspace/state/tacti_cr/events.jsonl")
QUIESCE_ENV = "OPENCLAW_QUIESCE"
PROTECTED_PATH = Path("workspace/state/tacti_cr/events.jsonl")
_QUIESCE_SKIP_LOGGED: set[str] = set()


def _utc_iso_z(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _coerce_json(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    try:
        json.dumps(payload, ensure_ascii=True)
    except TypeError as exc:
        raise TypeError("payload must be JSON-serializable") from exc
    return payload


def _resolve(path: Path | str | None = None) -> Path:
    target = Path(path) if path is not None else DEFAULT_PATH
    if target.is_absolute():
        return target
    root = Path(__file__).resolve().parents[2]
    return root / target


def _is_quiesced() -> bool:
    return str(os.getenv(QUIESCE_ENV, "")).strip() == "1"


def _is_protected_target(path: Path) -> bool:
    root = Path(__file__).resolve().parents[2]
    protected = (root / PROTECTED_PATH).resolve()
    try:
        return path.resolve() == protected
    except Exception:
        return str(path) == str(protected)


def _log_quiesce_skip_once(path: Path) -> None:
    key = str(path)
    if key in _QUIESCE_SKIP_LOGGED:
        return
    _QUIESCE_SKIP_LOGGED.add(key)
    print(f'QUIESCE_SKIP_WRITE file="{path}"', file=sys.stderr)


def emit(event_type: str, payload: dict, *, now: datetime | None = None, session_id: str | None = None) -> None:
    path = _resolve()
    if _is_quiesced() and _is_protected_target(path):
        _log_quiesce_skip_once(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(event_type, str) or not event_type.strip():
        return
    try:
        coerced_payload = _coerce_json(payload)
    except TypeError:
        coerced_payload = {"_stringified": str(payload)}
    row = {
        "ts": _utc_iso_z(now),
        "type": str(event_type),
        "payload": coerced_payload,
        "schema": 1,
    }
    if session_id:
        row["session_id"] = str(session_id)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    except Exception as exc:
        print(f"warning: tacti_cr.events emit failed: {exc}", file=sys.stderr)


def read_events(path: Path | str | None = None) -> Iterable[dict[str, Any]]:
    target = _resolve(path)
    if not target.exists():
        return []
    out: list[dict[str, Any]] = []
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            raise ValueError(f"malformed jsonl at line {lineno}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"malformed event object at line {lineno}")
        out.append(row)
    return out


def summarize_by_type(path: Path | str | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in read_events(path):
        key = str(row.get("type") or row.get("event") or "")
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


__all__ = ["DEFAULT_PATH", "emit", "read_events", "summarize_by_type", "_coerce_json"]
