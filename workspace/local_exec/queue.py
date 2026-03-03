from __future__ import annotations

import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validation import validate_job, validate_payload_for_job_type, validator_mode


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_dir(repo_root: Path) -> Path:
    path = repo_root / "workspace" / "local_exec" / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_path(repo_root: Path) -> Path:
    return _state_dir(repo_root) / "jobs.jsonl"


def lock_path(repo_root: Path) -> Path:
    return _state_dir(repo_root) / "jobs.lock"


def _append_event(repo_root: Path, event: dict[str, Any]) -> None:
    target = ledger_path(repo_root)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def enqueue_job(repo_root: Path, job: dict[str, Any]) -> dict[str, Any]:
    validate_job(job)
    validate_payload_for_job_type(job["job_type"], job["payload"])
    event = {
        "ts_utc": _utc_now(),
        "event": "enqueue",
        "validator_mode": validator_mode(),
        "job": job,
    }
    _append_event(repo_root, event)
    return event


def _iter_events(repo_root: Path) -> list[dict[str, Any]]:
    path = ledger_path(repo_root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def snapshots(repo_root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    now = time.time()
    for row in _iter_events(repo_root):
        if row.get("event") == "enqueue":
            job = row.get("job", {})
            jid = job.get("job_id")
            if not isinstance(jid, str):
                continue
            out[jid] = {
                "job": job,
                "state": "queued",
                "lease_expires_unix": None,
                "claimed_by": None,
                "updated_ts": row.get("ts_utc"),
            }
        else:
            jid = row.get("job_id")
            if not isinstance(jid, str) or jid not in out:
                continue
            snap = out[jid]
            ev = row.get("event")
            if ev == "claim":
                snap["state"] = "running"
                snap["claimed_by"] = row.get("worker_id")
                snap["lease_expires_unix"] = float(row.get("lease_expires_unix", 0))
            elif ev == "heartbeat":
                snap["lease_expires_unix"] = float(row.get("lease_expires_unix", 0))
            elif ev == "complete":
                snap["state"] = "complete"
            elif ev == "fail":
                snap["state"] = "failed"
            snap["updated_ts"] = row.get("ts_utc")

    for snap in out.values():
        if snap["state"] == "running":
            lease = snap.get("lease_expires_unix")
            if lease is not None and float(lease) <= now:
                snap["state"] = "queued"
                snap["claimed_by"] = None
                snap["lease_expires_unix"] = None
    return out


def claim_next_job(repo_root: Path, worker_id: str, lease_sec: int) -> dict[str, Any] | None:
    _state_dir(repo_root)
    lp = lock_path(repo_root)
    fd = os.open(lp, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        snaps = snapshots(repo_root)
        for jid in sorted(snaps.keys()):
            snap = snaps[jid]
            if snap["state"] != "queued":
                continue
            lease_expires = time.time() + lease_sec
            event = {
                "ts_utc": _utc_now(),
                "event": "claim",
                "job_id": jid,
                "worker_id": worker_id,
                "lease_expires_unix": lease_expires,
            }
            _append_event(repo_root, event)
            return snap["job"]
        return None
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def heartbeat(repo_root: Path, job_id: str, worker_id: str, lease_sec: int) -> None:
    event = {
        "ts_utc": _utc_now(),
        "event": "heartbeat",
        "job_id": job_id,
        "worker_id": worker_id,
        "lease_expires_unix": time.time() + lease_sec,
    }
    _append_event(repo_root, event)


def complete_job(repo_root: Path, job_id: str, worker_id: str, result: dict[str, Any]) -> None:
    event = {
        "ts_utc": _utc_now(),
        "event": "complete",
        "job_id": job_id,
        "worker_id": worker_id,
        "result": result,
    }
    _append_event(repo_root, event)


def fail_job(repo_root: Path, job_id: str, worker_id: str, error: str) -> None:
    event = {
        "ts_utc": _utc_now(),
        "event": "fail",
        "job_id": job_id,
        "worker_id": worker_id,
        "error": error,
    }
    _append_event(repo_root, event)
