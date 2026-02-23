#!/usr/bin/env python3
"""Deterministic pairing preflight with single-shot remediation."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


PAIRING_MISSING = "PAIRING_MISSING"
PAIRING_STALE = "PAIRING_STALE"
PAIRING_LOCKED = "PAIRING_LOCKED"
PAIRING_REMOTE_REQUIRED = "PAIRING_REMOTE_REQUIRED"
PAIRING_REMEDIATION_FAILED = "PAIRING_REMEDIATION_FAILED"
PAIRING_OK = "OK"

DEFAULT_COOLDOWN_SECONDS = int(os.environ.get("OPENCLAW_PAIRING_REPAIR_COOLDOWN_SEC", "45"))
_PRECHECK_LOCK = threading.Lock()
_ATTEMPTED_BY_CORR: set[str] = set()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state_path() -> Path:
    base = Path(
        os.environ.get("OPENCLAW_PAIRING_STATE_PATH")
        or (Path.home() / ".local" / "share" / "openclaw" / "pairing" / "preflight_state.json")
    ).expanduser()
    return base


def _guard_script_path() -> Path:
    return Path(__file__).resolve().parent / "check_gateway_pairing_health.sh"


def _run_cmd(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", f"{type(exc).__name__}:{exc}"


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _parse_reason(rc: int, out: str, err: str) -> tuple[str, str]:
    combined = f"{out}\n{err}".lower()
    if rc == 3 or "pairing required" in combined:
        return (
            PAIRING_REMOTE_REQUIRED,
            "run `openclaw pairing list` and confirm gateway scope is paired before retrying spawn",
        )
    if rc == 2 or "pending pairing" in combined or "pending" in combined:
        return (
            PAIRING_STALE,
            "run `openclaw pairing list --json` then rerun `workspace/scripts/check_gateway_pairing_health.sh`",
        )
    return (
        PAIRING_REMEDIATION_FAILED,
        "run `workspace/scripts/check_gateway_pairing_health.sh` and inspect `openclaw gateway status` output",
    )


def _base_result(ok: bool, reason: str, remedy: str, corr_id: str, **kwargs) -> dict:
    out = {
        "ok": bool(ok),
        "reason": str(reason),
        "remedy": str(remedy),
        "ts": _now_iso(),
        "corr_id": str(corr_id or "pairing_preflight"),
    }
    out.update(kwargs)
    return out


def ensure_pairing_healthy(
    *,
    corr_id: str = "pairing_preflight",
    guard_path: Path | None = None,
    run_guard: Callable[[], tuple[int, str, str]] | None = None,
    run_repair: Callable[[], tuple[int, str, str]] | None = None,
    cooldown_seconds: int | None = None,
    state_path: Path | None = None,
) -> dict:
    """Run pairing preflight and attempt one bounded remediation when stale."""
    if not _PRECHECK_LOCK.acquire(blocking=False):
        return _base_result(
            False,
            PAIRING_LOCKED,
            "wait for in-flight pairing preflight to finish, then retry spawn",
            corr_id,
            observations={"phase": "lock", "detail": "preflight_inflight"},
        )
    try:
        guard = Path(guard_path or _guard_script_path())
        if not guard.exists():
            return _base_result(
                False,
                PAIRING_MISSING,
                "restore `workspace/scripts/check_gateway_pairing_health.sh` and rerun preflight",
                corr_id,
                observations={"phase": "guard", "path": str(guard)},
            )

        guard_runner = run_guard or (lambda: _run_cmd([str(guard)], timeout=20))
        repair_runner = run_repair or (lambda: _run_cmd(["openclaw", "pairing", "list", "--json"], timeout=12))
        rc, out, err = guard_runner()
        if rc == 0:
            return _base_result(True, PAIRING_OK, "none", corr_id, observations={"guard_rc": rc})

        reason, remedy = _parse_reason(rc, out, err)
        if reason != PAIRING_STALE:
            return _base_result(
                False,
                reason,
                remedy,
                corr_id,
                observations={"guard_rc": rc, "guard_summary": "\n".join((out or err).splitlines()[:3])},
            )

        if corr_id in _ATTEMPTED_BY_CORR:
            return _base_result(
                False,
                PAIRING_REMEDIATION_FAILED,
                "single-shot remediation already attempted for this corr_id; investigate pairing state",
                corr_id,
                observations={"phase": "repair", "detail": "already_attempted"},
            )

        state_file = Path(state_path or _state_path()).expanduser()
        state = _load_state(state_file)
        now_ts = time.time()
        cooldown = float(DEFAULT_COOLDOWN_SECONDS if cooldown_seconds is None else cooldown_seconds)
        last_ts = float(state.get("last_repair_ts", 0) or 0)
        if now_ts - last_ts < cooldown:
            remaining = max(0, int(cooldown - (now_ts - last_ts)))
            return _base_result(
                False,
                PAIRING_LOCKED,
                f"pairing remediation cooldown active; retry after {remaining}s",
                corr_id,
                observations={"phase": "repair", "cooldown_remaining_sec": remaining},
            )

        _ATTEMPTED_BY_CORR.add(corr_id)
        repair_rc, repair_out, repair_err = repair_runner()
        state.update({"last_repair_ts": now_ts, "last_corr_id": corr_id})
        _save_state(state_file, state)
        if repair_rc != 0:
            return _base_result(
                False,
                PAIRING_REMEDIATION_FAILED,
                "repair command failed; run `openclaw pairing list --json` manually and check gateway service",
                corr_id,
                observations={
                    "phase": "repair",
                    "repair_rc": repair_rc,
                    "repair_summary": "\n".join((repair_out or repair_err).splitlines()[:3]),
                },
            )

        retry_rc, retry_out, retry_err = guard_runner()
        if retry_rc == 0:
            return _base_result(
                True,
                PAIRING_STALE,
                "pairing stale state refreshed; safe to retry spawn once now",
                corr_id,
                safe_to_retry_now=True,
                repair_attempted=True,
                observations={"guard_rc": rc, "retry_guard_rc": retry_rc},
            )

        return _base_result(
            False,
            PAIRING_REMEDIATION_FAILED,
            "pairing still unhealthy after remediation; run gateway repair and retry later",
            corr_id,
            observations={
                "phase": "post_repair_guard",
                "retry_guard_rc": retry_rc,
                "retry_guard_summary": "\n".join((retry_out or retry_err).splitlines()[:3]),
            },
        )
    finally:
        _PRECHECK_LOCK.release()


def _reset_for_tests() -> None:
    _ATTEMPTED_BY_CORR.clear()


if __name__ == "__main__":
    print(json.dumps(ensure_pairing_healthy(), indent=2))
