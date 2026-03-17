"""Shared Oracle priority lease helpers.

Oracle requests can temporarily claim the local model lane. Other preemptable
work should wait for the lease to clear before resuming.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
ORACLE_PRIORITY_STATE_PATH = WORKSPACE_ROOT / "state_runtime" / "oracle_priority.json"
DEFAULT_TTL_SECONDS = 90.0
DEFAULT_WAIT_SECONDS = 45.0


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".{time.time_ns()}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def get_active_lease(*, now: float | None = None) -> dict[str, Any] | None:
    now = float(now if now is not None else time.time())
    payload = _read_json(ORACLE_PRIORITY_STATE_PATH)
    if not isinstance(payload, dict):
        return None
    try:
        expires_at = float(payload.get("expires_at") or 0.0)
    except Exception:
        expires_at = 0.0
    if expires_at > now:
        return payload
    try:
        ORACLE_PRIORITY_STATE_PATH.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return None


def acquire_lease(
    owner: str,
    *,
    purpose: str = "oracle",
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    metadata: dict[str, Any] | None = None,
    max_wait_seconds: float = 5.0,
    poll_interval: float = 0.1,
) -> dict[str, Any] | None:
    owner = str(owner or "").strip()
    if not owner:
        raise ValueError("owner is required")
    deadline = time.time() + max(0.0, float(max_wait_seconds))
    while True:
        active = get_active_lease()
        if active is None or str(active.get("owner") or "") == owner:
            now = time.time()
            payload = {
                "owner": owner,
                "purpose": str(purpose or "oracle"),
                "acquired_at": now,
                "expires_at": now + max(1.0, float(ttl_seconds)),
                "metadata": dict(metadata or {}),
            }
            _write_json_atomic(ORACLE_PRIORITY_STATE_PATH, payload)
            confirmed = get_active_lease()
            if confirmed is not None and str(confirmed.get("owner") or "") == owner:
                return confirmed
        if time.time() >= deadline:
            return None
        time.sleep(max(0.01, float(poll_interval)))


def release_lease(owner: str) -> bool:
    active = get_active_lease()
    if active is None:
        return True
    if str(active.get("owner") or "") != str(owner or ""):
        return False
    try:
        ORACLE_PRIORITY_STATE_PATH.unlink()
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


def wait_for_clear(
    *,
    max_wait_seconds: float = DEFAULT_WAIT_SECONDS,
    poll_interval: float = 0.25,
) -> dict[str, Any]:
    started = time.time()
    deadline = started + max(0.0, float(max_wait_seconds))
    active = get_active_lease()
    while active is not None and time.time() < deadline:
        time.sleep(max(0.01, float(poll_interval)))
        active = get_active_lease()
    waited_seconds = max(0.0, time.time() - started)
    return {
        "cleared": active is None,
        "waited_seconds": waited_seconds,
        "active": active,
    }


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "DEFAULT_WAIT_SECONDS",
    "ORACLE_PRIORITY_STATE_PATH",
    "acquire_lease",
    "get_active_lease",
    "release_lease",
    "wait_for_clear",
]
