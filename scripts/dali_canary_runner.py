#!/usr/bin/env python3
"""Opt-in Dali canary runner (manual CLI + timer-ready)."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT / "workspace" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))

from event_envelope import append_envelope, make_envelope


LINE_RE = re.compile(
    r"^CANARY status=(OK|DEGRADED|FAIL) coder=(UP|DOWN|DEGRADED) replay=(WRITABLE|NOACCESS) pairing=(OK|UNHEALTHY) ts=([0-9TZ:\-]+)$"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runtime_canary_log_path() -> Path:
    raw = os.environ.get("OPENCLAW_CANARY_LOG_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share" / "openclaw" / "canary" / "canary.log"


def runtime_envelope_log_path() -> Path:
    raw = os.environ.get("OPENCLAW_EVENT_ENVELOPE_LOG_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share" / "openclaw" / "events" / "gate_health.jsonl"


def replay_log_path() -> Path:
    raw = os.environ.get("OPENCLAW_REPLAY_LOG_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share" / "openclaw" / "replay" / "replay.jsonl"


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except Exception as exc:
        return 1, "", f"{type(exc).__name__}:{exc}"


def parse_diag_markers(text: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("-"):
            continue
        if "=" not in s:
            continue
        key, value = s.split("=", 1)
        key = key.strip()
        if not key:
            continue
        markers[key] = value.strip()
    return markers


def run_provider_diag() -> dict[str, Any]:
    cmd = ["node", str(REPO_ROOT / "scripts" / "system2" / "provider_diag.js")]
    rc, out, err = _run(cmd, timeout=30)
    markers = parse_diag_markers(out)
    coder = markers.get("coder_status", "DOWN")
    if coder not in {"UP", "DOWN", "DEGRADED"}:
        coder = "DOWN"
    return {
        "ok": rc == 0,
        "markers": markers,
        "coder": coder,
        "stderr": err.strip(),
    }


def replay_writable() -> tuple[str, str | None]:
    target = replay_log_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8"):
            pass
        return "WRITABLE", None
    except Exception as exc:
        return "NOACCESS", f"{type(exc).__name__}:{exc}"


def pairing_canary() -> tuple[str, str | None]:
    guard = REPO_ROOT / "workspace" / "scripts" / "check_gateway_pairing_health.sh"
    if not guard.exists():
        return "UNHEALTHY", "pairing_guard_missing"
    rc, _out, err = _run([str(guard)], timeout=20)
    if rc == 0:
        return "OK", None
    return "UNHEALTHY", (err.strip() or "pairing_guard_failed")[:240]


def status_from_components(*, diag_ok: bool, coder: str, replay: str, pairing: str) -> str:
    if not diag_ok or pairing == "UNHEALTHY":
        return "FAIL"
    if coder != "UP" or replay != "WRITABLE":
        return "DEGRADED"
    return "OK"


def exit_code_for_status(status: str) -> int:
    if status == "OK":
        return 0
    if status == "DEGRADED":
        return 10
    return 20


def format_line(*, status: str, coder: str, replay: str, pairing: str, ts: str) -> str:
    line = f"CANARY status={status} coder={coder} replay={replay} pairing={pairing} ts={ts}"
    if not LINE_RE.match(line):
        raise ValueError("invalid canary line format")
    return line


def append_line(path: Path, line: str) -> str | None:
    path = Path(path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return None
    except Exception as exc:
        return f"{type(exc).__name__}:{exc}"


def main() -> int:
    corr_id = os.environ.get("OPENCLAW_CANARY_CORR_ID", "canary")
    ts = now_iso()

    diag = run_provider_diag()
    replay, replay_note = replay_writable()
    pairing, pairing_note = pairing_canary()
    status = status_from_components(diag_ok=bool(diag.get("ok")), coder=str(diag.get("coder")), replay=replay, pairing=pairing)

    line = format_line(status=status, coder=str(diag.get("coder")), replay=replay, pairing=pairing, ts=ts)
    print(line)
    canary_log_error = append_line(runtime_canary_log_path(), line)

    details = {
        "status": status,
        "coder": str(diag.get("coder")),
        "replay": replay,
        "pairing": pairing,
        "diag_ok": bool(diag.get("ok")),
        "coder_degraded_reason": str(diag.get("markers", {}).get("coder_degraded_reason", "")),
        "replay_note": replay_note,
        "pairing_note": pairing_note,
        "canary_log_error": canary_log_error,
    }
    env = make_envelope(
        event="canary_runner",
        severity=("INFO" if status == "OK" else ("WARN" if status == "DEGRADED" else "ERROR")),
        component="dali_canary_runner",
        corr_id=corr_id,
        details=details,
        ts=ts,
    )
    append_envelope(runtime_envelope_log_path(), env)

    return exit_code_for_status(status)


if __name__ == "__main__":
    raise SystemExit(main())
