#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from contract_policy import contract_forces_code_override  # type: ignore  # noqa: E402

GPU_STATE = Path(os.environ.get("OPENCLAW_GPU_STATE_DIR") or (ROOT / "workspace" / "state_runtime" / "gpu"))
LAST_ACTIVITY = GPU_STATE / "last_activity.json"
CONTRACT_PATH = Path(
    os.environ.get("OPENCLAW_CONTRACT_CURRENT")
    or (ROOT / "workspace" / "state_runtime" / "contract" / "current.json")
)
EVENTS_PATH = Path(
    os.environ.get("OPENCLAW_CONTRACT_EVENTS")
    or (ROOT / "workspace" / "state_runtime" / "contract" / "events.jsonl")
)
UNIT = os.environ.get("OPENCLAW_IDLE_REAPER_UNIT", "openclaw-tool-coder-vllm-models.service")
TOOL = "coder_vllm.models"
DEFAULT_IDLE_MINUTES = 15


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_stamp() -> str:
    return now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_z(value: str | None) -> Optional[dt.datetime]:
    s = str(value or "")
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_event(event: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def log_action(*, action: str, reason: str, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "ts": utc_stamp(),
        "type": "idle_reaper_action",
        "tool": TOOL,
        "action": action,
        "reason": reason,
    }
    payload.update(extra)
    append_event(payload)


def service_active() -> bool:
    if os.environ.get("OPENCLAW_IDLE_REAPER_FORCE_SERVICE_INACTIVE") == "1":
        return False
    proc = subprocess.run(
        ["systemctl", "--user", "is-active", UNIT],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "active"


def stop_service() -> None:
    subprocess.run(["systemctl", "--user", "stop", UNIT], capture_output=True, text=True, check=False)


def release_gpu_lock() -> None:
    lock_script = ROOT / "workspace" / "scripts" / "gpu_lock.py"
    if lock_script.exists():
        subprocess.run([str(lock_script), "release", "--holder", TOOL], capture_output=True, text=True, check=False)


def main() -> int:
    idle_minutes = max(1, int(os.environ.get("OPENCLAW_IDLE_MINUTES", str(DEFAULT_IDLE_MINUTES))))
    now = now_utc()

    contract = load_json(CONTRACT_PATH, {})
    if not isinstance(contract, dict):
        contract = {}

    if contract_forces_code_override(contract):
        log_action(action="noop", reason="forced_code_override")
        print(json.dumps({"ok": True, "action": "noop", "reason": "forced_code_override"}, indent=2, sort_keys=True))
        return 0

    if not service_active():
        log_action(action="noop", reason="service_not_active")
        print(json.dumps({"ok": True, "action": "noop", "reason": "service_not_active"}, indent=2, sort_keys=True))
        return 0

    last = load_json(LAST_ACTIVITY, {})
    if not isinstance(last, dict):
        last = {}
    tool_row = last.get(TOOL) if isinstance(last.get(TOOL), dict) else {}
    ts = str(tool_row.get("ts", ""))
    last_ts = parse_z(ts)

    if last_ts is None:
        last[TOOL] = {"ts": utc_stamp(), "source": "reaper_init"}
        save_json(LAST_ACTIVITY, last)
        log_action(action="noop", reason="no_last_activity_initialized")
        print(
            json.dumps(
                {"ok": True, "action": "noop", "reason": "no_last_activity_initialized"},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    idle_for = now - last_ts
    if idle_for < dt.timedelta(minutes=idle_minutes):
        log_action(action="noop", reason="not_idle", idle_seconds=int(idle_for.total_seconds()))
        print(
            json.dumps(
                {
                    "ok": True,
                    "action": "noop",
                    "reason": "not_idle",
                    "idle_seconds": int(idle_for.total_seconds()),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    stop_service()
    release_gpu_lock()
    append_event({"ts": utc_stamp(), "type": "idle_reap", "tool": TOOL, "idle_minutes": idle_minutes, "last_activity_ts": ts})
    log_action(action="stopped", reason="idle_timeout_reached", idle_minutes=idle_minutes, last_activity_ts=ts)
    print(
        json.dumps(
            {
                "ok": True,
                "action": "stopped",
                "tool": TOOL,
                "idle_minutes": idle_minutes,
                "last_activity_ts": ts,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
