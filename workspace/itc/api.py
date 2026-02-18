from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .ingest.interfaces import DEFAULT_ARTIFACT_ROOT, emit_event, validate_signal


def _parse_iso(ts_utc: str) -> datetime:
    return datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _parse_lookback(value: str) -> timedelta:
    unit = value[-1]
    qty = int(value[:-1])
    if unit == "m":
        return timedelta(minutes=qty)
    if unit == "h":
        return timedelta(hours=qty)
    if unit == "d":
        return timedelta(days=qty)
    raise ValueError(f"invalid_lookback:{value}")


def _artifact_root_from_policy(policy: Optional[Dict[str, Any]]) -> Path:
    if policy and policy.get("artifacts_root"):
        return Path(policy["artifacts_root"])
    return DEFAULT_ARTIFACT_ROOT


def get_itc_signal(ts_utc: str, lookback: str = "8h", policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return best available ITC signal for timestamp with reason codes.

    Output shape:
      {"reason": "ok|missing|stale|invalid", "signal": dict|None, "age_seconds": int|None}
    """
    query_ts = _parse_iso(ts_utc)
    max_age = _parse_lookback(lookback)
    artifact_root = _artifact_root_from_policy(policy)
    normalized_root = artifact_root / "normalized"
    run_id = str(policy.get("run_id")) if policy else "itc_api"

    if not normalized_root.exists():
        emit_event("itc_signal_rejected", run_id, {"reason": "missing", "ts_utc": ts_utc}, artifact_root)
        return {"reason": "missing", "signal": None, "age_seconds": None}

    latest_valid = None
    latest_valid_ts = None
    invalid_seen = False

    for path in sorted(normalized_root.rglob("itc_signal_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid_seen = True
            continue

        ok, _ = validate_signal(data)
        if not ok:
            invalid_seen = True
            continue

        sig_ts = _parse_iso(data["ts_utc"])
        if sig_ts > query_ts:
            continue

        if latest_valid_ts is None or sig_ts > latest_valid_ts:
            latest_valid = data
            latest_valid_ts = sig_ts

    if latest_valid is None:
        reason = "invalid" if invalid_seen else "missing"
        emit_event("itc_signal_rejected", run_id, {"reason": reason, "ts_utc": ts_utc}, artifact_root)
        return {"reason": reason, "signal": None, "age_seconds": None}

    age = query_ts - latest_valid_ts
    age_seconds = int(age.total_seconds())
    if age > max_age:
        emit_event(
            "itc_signal_rejected",
            run_id,
            {"reason": "stale", "ts_utc": ts_utc, "signal_ts": latest_valid["ts_utc"], "age_seconds": age_seconds},
            artifact_root,
        )
        return {"reason": "stale", "signal": None, "age_seconds": age_seconds}

    emit_event(
        "itc_signal_selected",
        run_id,
        {
            "ts_utc": ts_utc,
            "signal_ts": latest_valid["ts_utc"],
            "age_seconds": age_seconds,
            "source": latest_valid.get("source"),
        },
        artifact_root,
    )
    return {
        "reason": "ok",
        "signal": latest_valid,
        "age_seconds": age_seconds,
    }
