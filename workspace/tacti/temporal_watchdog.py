"""Temporal coherence watchdog and beacon utilities."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_int, is_enabled
from .events import emit


ISO_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?)\b")


def _to_dt(text: str) -> datetime | None:
    try:
        value = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def beacon_path(repo_root: Path | None = None) -> Path:
    root = Path(repo_root or Path(__file__).resolve().parents[2])
    return root / "workspace" / "state" / "temporal" / "beacon.json"


def update_beacon(repo_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    path = beacon_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "epoch_ms": int(now.timestamp() * 1000),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    emit("tacti_cr.temporal_watchdog.beacon_updated", {"path": str(path), "epoch_ms": payload["epoch_ms"]}, now=now)
    return {"ok": True, "path": str(path), **payload}


def load_beacon(repo_root: Path | None = None) -> dict[str, Any]:
    path = beacon_path(repo_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def detect_temporal_drift(
    text: str,
    *,
    now: datetime | None = None,
    beacon: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    beacon = beacon or {}
    findings: list[dict[str, Any]] = []

    beacon_dt = _to_dt(str(beacon.get("updated_at", "")))
    stale_limit_min = get_int("temporal_stale_limit_minutes", 20, clamp=(1, 360))
    future_done_min = get_int("temporal_future_done_minutes", 5, clamp=(1, 180))

    if beacon_dt and (now - beacon_dt).total_seconds() > stale_limit_min * 60:
        findings.append(
            {
                "type": "stale_context_treated_fresh",
                "detail": f"beacon_age_minutes>{stale_limit_min}",
                "score": 0.8,
            }
        )

    seen_ts: list[datetime] = []
    for match in ISO_PATTERN.findall(text or ""):
        dt = _to_dt(match)
        if dt:
            seen_ts.append(dt)

    for dt in seen_ts:
        if "done" in (text or "").lower() and (dt - now).total_seconds() > future_done_min * 60:
            findings.append(
                {
                    "type": "future_event_marked_done",
                    "detail": dt.isoformat(),
                    "score": 0.95,
                }
            )

    for prev, cur in zip(seen_ts, seen_ts[1:]):
        if cur < prev:
            findings.append(
                {
                    "type": "sequence_violation",
                    "detail": f"{prev.isoformat()}->{cur.isoformat()}",
                    "score": 0.75,
                }
            )

    return findings


def temporal_reset_event(
    text: str,
    *,
    now: datetime | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    if not is_enabled("temporal_watchdog"):
        return None
    now = now or datetime.now(timezone.utc)
    beacon = load_beacon(repo_root)
    findings = detect_temporal_drift(text, now=now, beacon=beacon)
    if not findings:
        return None

    digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]
    event = {
        "event": "temporal_reset",
        "ts": now.isoformat().replace("+00:00", "Z"),
        "content_hash": digest,
        "findings": findings,
        "action": "reanchor_today_memory_and_beacon",
    }
    emit("tacti_cr.temporal_watchdog.temporal_reset", {"content_hash": digest, "findings": findings}, now=now)
    return event


__all__ = [
    "beacon_path",
    "update_beacon",
    "load_beacon",
    "detect_temporal_drift",
    "temporal_reset_event",
]
