#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
from typing import Any, Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_STATE_DIR = os.path.join(ROOT, "workspace", "state_runtime", "contract")
STATE_DIR = os.path.abspath(os.environ.get("OPENCLAW_CONTRACT_STATE_DIR", DEFAULT_STATE_DIR))
CURRENT = os.path.join(STATE_DIR, "current.json")
EVENTS = os.path.join(STATE_DIR, "events.jsonl")
SIGNALS = os.path.join(STATE_DIR, "signals", "activity.jsonl")
MANAGER = os.path.join(ROOT, "workspace", "scripts", "contract_manager.py")


def now_utc_dt() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def utc_now() -> str:
    return now_utc_dt().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_duration(value: str) -> datetime.timedelta:
    s = str(value or "").strip().lower()
    total = datetime.timedelta(0)
    num = ""
    for ch in s:
        if ch.isdigit():
            num += ch
            continue
        if ch not in ("h", "m"):
            continue
        if not num:
            continue
        n = int(num)
        num = ""
        if ch == "h":
            total += datetime.timedelta(hours=n)
        else:
            total += datetime.timedelta(minutes=n)
    if total.total_seconds() <= 0:
        raise ValueError("bad duration")
    return total


def load_json(path: str, default: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        return default
    return default


def save_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def append_event(event: Dict[str, Any]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(EVENTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def signal(kind: str, meta: Optional[Dict[str, Any]] = None) -> None:
    os.makedirs(os.path.dirname(SIGNALS), exist_ok=True)
    payload = {"ts": utc_now(), "kind": kind, "meta": meta or {}}
    with open(SIGNALS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def cmd_status(_: argparse.Namespace) -> None:
    state = load_json(CURRENT, None)
    print(json.dumps(state, indent=2, sort_keys=True))


def cmd_tick(_: argparse.Namespace) -> None:
    env = dict(os.environ)
    env["OPENCLAW_CONTRACT_STATE_DIR"] = STATE_DIR
    proc = subprocess.run([MANAGER], capture_output=True, text=True, env=env)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def cmd_set_mode(args: argparse.Namespace) -> None:
    state = load_json(CURRENT, None)
    if not state:
        cmd_tick(args)
        state = load_json(CURRENT, {})

    now = utc_now()
    ttl_until = None
    if args.ttl:
        ttl = parse_duration(args.ttl)
        ttl_until = (now_utc_dt() + ttl).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    override = {
        "mode": args.mode,
        "ttl_until": ttl_until,
        "reason": args.reason or "manual",
        "set_ts": now,
    }
    state["override"] = override
    state["mode"] = args.mode
    state["source"] = "MANUAL"
    state["ts"] = now
    save_json(CURRENT, state)
    append_event({"ts": now, "type": "override_set", "override": override})
    signal("manual_override", {"mode": args.mode, "ttl_until": ttl_until, "reason": override["reason"]})
    print(json.dumps({"ok": True, "mode": args.mode, "ttl_until": ttl_until}, indent=2, sort_keys=True))


def cmd_clear_override(_: argparse.Namespace) -> None:
    state = load_json(CURRENT, None) or {}
    now = utc_now()
    prev = state.get("override")
    state["override"] = None
    state["ts"] = now
    save_json(CURRENT, state)
    append_event({"ts": now, "type": "override_cleared", "override": prev})
    signal("manual_override_cleared", {})
    print(json.dumps({"ok": True}, indent=2, sort_keys=True))


def cmd_ping(args: argparse.Namespace) -> None:
    signal(args.kind, {"note": args.note or ""})
    print(json.dumps({"ok": True, "kind": args.kind}, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("tick")

    p_mode = sub.add_parser("set-mode")
    p_mode.add_argument("mode", choices=["SERVICE", "CODE"])
    p_mode.add_argument("--ttl", help="e.g., 6h, 90m, 1h30m")
    p_mode.add_argument("--reason", help="override reason")

    sub.add_parser("clear-override")

    p_ping = sub.add_parser("ping")
    p_ping.add_argument("kind", choices=["service_request", "tool_call", "manual_ping"])
    p_ping.add_argument("--note")

    args = parser.parse_args()
    if args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "tick":
        cmd_tick(args)
    elif args.cmd == "set-mode":
        cmd_set_mode(args)
    elif args.cmd == "clear-override":
        cmd_clear_override(args)
    elif args.cmd == "ping":
        cmd_ping(args)


if __name__ == "__main__":
    main()
