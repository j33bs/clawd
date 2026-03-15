from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, load_json, utc_now_iso
from .logging_utils import JsonlLogger
from .paths import FISHTANK_CONTROL_STATE_PATH, FISHTANK_STATE_PATH, RUNTIME_LOGS, ensure_runtime_dirs

REQUESTED_MODES = {"on", "off", "auto"}
SCHEDULE_NUDGE_REASONS = {"window_start", "window_end", "manual"}


def normalize_requested_mode(mode: str | None) -> str:
    normalized = str(mode or "auto").strip().lower()
    return normalized if normalized in REQUESTED_MODES else "auto"


def requested_mode_to_manual_override(mode: str | None) -> str:
    normalized = normalize_requested_mode(mode)
    if normalized == "auto":
        return "none"
    return normalized


def manual_override_to_requested_mode(mode: str | None) -> str:
    normalized = str(mode or "none").strip().lower()
    if normalized in {"on", "off"}:
        return normalized
    return "auto"


def _logger() -> JsonlLogger:
    return JsonlLogger(RUNTIME_LOGS / "dali_cathedral_runtime.log")


def _control_path(path: Path | None = None) -> Path:
    return path or FISHTANK_CONTROL_STATE_PATH


def _state_path(path: Path | None = None) -> Path:
    return path or FISHTANK_STATE_PATH


def load_control_state(path: Path | None = None) -> dict[str, Any]:
    payload = load_json(_control_path(path), {})
    if not isinstance(payload, dict):
        payload = {}
    requested_mode = normalize_requested_mode(payload.get("requested_mode") or manual_override_to_requested_mode(payload.get("manual_override_mode")))
    payload["requested_mode"] = requested_mode
    payload["manual_override_mode"] = requested_mode_to_manual_override(requested_mode)
    payload["control_source"] = str(payload.get("control_source") or payload.get("source") or "unknown")
    payload["last_control_ts"] = str(payload.get("last_control_ts") or payload.get("updated_at") or "")
    payload["last_control_reason"] = str(payload.get("last_control_reason") or payload.get("reason") or "")
    payload["source"] = payload["control_source"]
    payload["updated_at"] = payload["last_control_ts"]
    payload["reason"] = payload["last_control_reason"]
    return payload


def load_live_state(path: Path | None = None) -> dict[str, Any]:
    payload = load_json(_state_path(path), {})
    return payload if isinstance(payload, dict) else {}


def ensure_control_state(
    *,
    path: Path | None = None,
    source: str = "control_api",
    reason: str = "initialize",
) -> dict[str, Any]:
    ensure_runtime_dirs()
    control_path = _control_path(path)
    if control_path.exists():
        return load_control_state(control_path)
    payload = {
        "requested_mode": "auto",
        "manual_override_mode": "none",
        "control_source": str(source),
        "last_control_ts": utc_now_iso(),
        "last_control_reason": str(reason),
        "source": str(source),
        "updated_at": utc_now_iso(),
        "reason": str(reason),
    }
    atomic_write_json(control_path, payload)
    return load_control_state(control_path)


def write_control_state(
    requested_mode: str,
    *,
    source: str,
    reason: str = "",
    path: Path | None = None,
    nudge: str = "",
) -> dict[str, Any]:
    ensure_runtime_dirs()
    control_path = _control_path(path)
    payload = ensure_control_state(path=control_path, source=source, reason="initialize")
    timestamp = utc_now_iso()
    normalized = normalize_requested_mode(requested_mode)
    payload["requested_mode"] = normalized
    payload["manual_override_mode"] = requested_mode_to_manual_override(normalized)
    payload["control_source"] = str(source)
    payload["last_control_ts"] = timestamp
    payload["last_control_reason"] = str(reason or "")
    payload["source"] = str(source)
    payload["updated_at"] = timestamp
    payload["reason"] = str(reason or "")
    if nudge:
        payload["last_schedule_nudge"] = str(nudge)
        payload["last_schedule_nudge_at"] = timestamp
    atomic_write_json(control_path, payload)
    return load_control_state(control_path)


def _status_payload(control_state: dict[str, Any], live_state: dict[str, Any]) -> dict[str, Any]:
    def _pid_alive(pid_value: Any) -> bool:
        try:
            pid = int(pid_value or 0)
        except Exception:
            return False
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _visible_attached(payload: dict[str, Any]) -> bool:
        display_mode_active = bool(payload.get("display_mode_active", False))
        display_attached = bool(payload.get("display_attached", False))
        window_visible = bool(payload.get("window_visible", False))
        fullscreen_requested = bool(payload.get("fullscreen_requested", True))
        fullscreen_attached = bool(payload.get("fullscreen_attached", False))
        monitor_bound = bool(payload.get("monitor_bound", False))
        if fullscreen_requested:
            return display_mode_active and display_attached and window_visible and fullscreen_attached and monitor_bound
        return display_mode_active and display_attached and window_visible

    requested_mode = normalize_requested_mode(control_state.get("requested_mode"))
    effective_mode = normalize_requested_mode(live_state.get("effective_mode") or requested_mode)
    runtime_instance_id = str(live_state.get("runtime_instance_id", "") or "")
    pid = int(live_state.get("pid", 0) or 0)
    visible_display_ok = _visible_attached(live_state)
    return {
        "ok": bool(live_state),
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "display_mode_active": bool(live_state.get("display_mode_active", False)),
        "reason": str(live_state.get("last_control_reason") or control_state.get("last_control_reason") or ""),
        "timestamp": str(live_state.get("last_control_ts") or control_state.get("last_control_ts") or ""),
        "control_source": str(live_state.get("control_source") or control_state.get("control_source") or "unknown"),
        "effective_activation_source": str(live_state.get("effective_activation_source", "") or ""),
        "runtime_instance_id": runtime_instance_id,
        "pid": pid,
        "start_ts": str(live_state.get("start_ts", "") or ""),
        "runtime_instance_alive": _pid_alive(pid),
        "window_visible": bool(live_state.get("window_visible", False)),
        "fullscreen_attached": bool(live_state.get("fullscreen_attached", False)),
        "monitor_bound": bool(live_state.get("monitor_bound", False)),
        "display_attached": bool(live_state.get("display_attached", False)),
        "last_display_attach_ts": str(live_state.get("last_display_attach_ts", "") or ""),
        "last_display_detach_ts": str(live_state.get("last_display_detach_ts", "") or ""),
        "last_control_apply_ts": str(live_state.get("last_control_apply_ts", "") or ""),
        "last_idle_activation_ts": str(live_state.get("last_idle_activation_ts", "") or ""),
        "visible_display_ok": bool(visible_display_ok),
        "control_state": control_state,
        "fishtank_state": live_state,
    }


def get_status(
    *,
    control_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    ensure_runtime_dirs()
    control_state = ensure_control_state(path=control_path)
    live_state = load_live_state(state_path)
    return _status_payload(control_state, live_state)


def set_mode(
    mode: str,
    *,
    source: str = "local",
    reason: str = "",
    wait: bool = True,
    wait_for: str = "mode",
    wait_timeout_s: float = 5.0,
    control_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    ensure_runtime_dirs()
    requested_mode = normalize_requested_mode(mode)
    logger = _logger()
    logger.log("CONTROL_REQUEST", source=str(source), requested=requested_mode, reason=str(reason or requested_mode))
    control_state = write_control_state(
        requested_mode,
        source=source,
        reason=reason or f"set_mode:{requested_mode}",
        path=control_path,
    )
    if not wait:
        live_state = load_live_state(state_path)
        return _status_payload(control_state, live_state) | {"ok": True}

    deadline = time.monotonic() + max(0.2, float(wait_timeout_s))
    last_live_state: dict[str, Any] = {}
    wait_for_mode = str(wait_for or "mode").strip().lower()
    if wait_for_mode not in {"mode", "visible", "hidden"}:
        wait_for_mode = "mode"

    def _visible(payload: dict[str, Any]) -> bool:
        display_mode_active = bool(payload.get("display_mode_active", False))
        display_attached = bool(payload.get("display_attached", False))
        window_visible = bool(payload.get("window_visible", False))
        fullscreen_requested = bool(payload.get("fullscreen_requested", True))
        fullscreen_attached = bool(payload.get("fullscreen_attached", False))
        monitor_bound = bool(payload.get("monitor_bound", False))
        if fullscreen_requested:
            return display_mode_active and display_attached and window_visible and fullscreen_attached and monitor_bound
        return display_mode_active and display_attached and window_visible

    def _hidden(payload: dict[str, Any]) -> bool:
        return (not bool(payload.get("display_mode_active", False))) and (not bool(payload.get("display_attached", False))) and (
            not bool(payload.get("window_visible", False))
        )

    while time.monotonic() <= deadline:
        last_live_state = load_live_state(state_path)
        if isinstance(last_live_state, dict):
            last_control_ts = str(last_live_state.get("last_control_ts") or "")
            effective_mode = normalize_requested_mode(last_live_state.get("effective_mode") or requested_mode)
            requested_live = normalize_requested_mode(last_live_state.get("requested_mode") or requested_mode)
            display_mode_active = bool(last_live_state.get("display_mode_active", False))
            control_applied = last_control_ts == control_state["last_control_ts"] and requested_live == requested_mode
            if requested_mode in {"on", "off"}:
                control_applied = control_applied and effective_mode == requested_mode
            if control_applied:
                if requested_mode == "on" and not display_mode_active:
                    time.sleep(0.1)
                    continue
                if requested_mode == "off" and display_mode_active:
                    time.sleep(0.1)
                    continue
                if wait_for_mode == "visible" and requested_mode == "on" and (not _visible(last_live_state)):
                    time.sleep(0.1)
                    continue
                if wait_for_mode == "hidden" and requested_mode == "off" and (not _hidden(last_live_state)):
                    time.sleep(0.1)
                    continue
                logger.log("CONTROL_APPLIED", source=str(source), requested=requested_mode, effective=effective_mode)
                return _status_payload(control_state, last_live_state) | {"ok": True}
        time.sleep(0.1)
    result = _status_payload(control_state, last_live_state)
    result["ok"] = False
    result["reason"] = "runtime_not_applied_within_timeout"
    return result


def record_schedule_nudge(
    reason: str,
    *,
    source: str = "runtime",
    path: Path | None = None,
) -> dict[str, Any]:
    ensure_runtime_dirs()
    normalized = str(reason or "manual").strip().lower()
    if normalized not in SCHEDULE_NUDGE_REASONS:
        normalized = "manual"
    logger = _logger()
    logger.log("SCHEDULE_NUDGE", reason=normalized, source=str(source))
    current = ensure_control_state(path=path, source=source, reason="initialize")
    return write_control_state(
        normalize_requested_mode(current.get("requested_mode")),
        source=source,
        reason=f"schedule_nudge:{normalized}",
        path=path,
        nudge=normalized,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DALI Cathedral control API")
    parser.add_argument("command", choices=["on", "off", "auto", "status"])
    parser.add_argument("--source", default="local")
    parser.add_argument("--reason", default="")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--wait-visible", action="store_true")
    parser.add_argument("--wait-hidden", action="store_true")
    parser.add_argument("--wait-timeout", type=float, default=5.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "status":
        payload = get_status()
    else:
        wait_for = "mode"
        if args.wait_visible and args.wait_hidden:
            payload = {
                "ok": False,
                "reason": "wait_visible_and_wait_hidden_are_mutually_exclusive",
                "requested_mode": str(args.command),
            }
            print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            return 2
        if args.wait_visible:
            wait_for = "visible"
        elif args.wait_hidden:
            wait_for = "hidden"
        payload = set_mode(
            args.command,
            source=str(args.source or "local"),
            reason=str(args.reason or ""),
            wait=not bool(args.no_wait),
            wait_for=wait_for,
            wait_timeout_s=float(args.wait_timeout),
        )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0 if bool(payload.get("ok", False) or args.command == "status") else 1


if __name__ == "__main__":
    raise SystemExit(main())
