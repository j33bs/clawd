#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_STATE = os.path.join(ROOT, "workspace", "state_runtime", "gpu")
STATE = os.path.abspath(os.environ.get("OPENCLAW_GPU_STATE_DIR", DEFAULT_STATE))
LOCK = os.path.join(STATE, "lock.json")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_stamp() -> str:
    return now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_z(value: str) -> Optional[dt.datetime]:
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


def load_lock() -> Optional[dict[str, Any]]:
    if not os.path.exists(LOCK):
        return None
    try:
        with open(LOCK, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def save_lock(payload: dict[str, Any]) -> None:
    os.makedirs(STATE, exist_ok=True)
    tmp = LOCK + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, LOCK)


def is_expired(lock: Optional[dict[str, Any]]) -> bool:
    ttl = parse_z((lock or {}).get("ttl_until", ""))
    return bool(ttl and now_utc() >= ttl)


def cmd_status(_: argparse.Namespace) -> int:
    lock = load_lock()
    if not lock:
        print(json.dumps({"held": False}, indent=2, sort_keys=True))
        return 0
    if is_expired(lock):
        print(json.dumps({"held": False, "stale": True, "previous": lock}, indent=2, sort_keys=True))
        return 0
    print(json.dumps({"held": True, **lock}, indent=2, sort_keys=True))
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    lock = load_lock()
    if lock and not is_expired(lock) and lock.get("holder") != args.holder:
        print(json.dumps({"ok": False, "reason": "held", "lock": lock}, indent=2, sort_keys=True))
        return 2

    ttl_until = now_utc() + dt.timedelta(minutes=max(1, int(args.ttl_minutes)))
    payload = {
        "holder": args.holder,
        "reason": args.reason,
        "ts": utc_stamp(),
        "ttl_until": ttl_until.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    save_lock(payload)
    print(json.dumps({"ok": True, **payload}, indent=2, sort_keys=True))
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    lock = load_lock()
    if not lock:
        print(json.dumps({"ok": True, "released": False}, indent=2, sort_keys=True))
        return 0
    if args.holder and lock.get("holder") != args.holder and not is_expired(lock):
        print(json.dumps({"ok": False, "reason": "not_holder", "lock": lock}, indent=2, sort_keys=True))
        return 3
    try:
        os.remove(LOCK)
    except FileNotFoundError:
        pass
    print(json.dumps({"ok": True, "released": True}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")

    p_claim = sub.add_parser("claim")
    p_claim.add_argument("--holder", required=True)
    p_claim.add_argument("--reason", default="use")
    p_claim.add_argument("--ttl-minutes", type=int, default=30)

    p_release = sub.add_parser("release")
    p_release.add_argument("--holder", default="")

    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "claim":
        return cmd_claim(args)
    if args.cmd == "release":
        return cmd_release(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
