#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_QUEUE_DIR = ROOT / "workspace" / "state_runtime" / "queue"
QUEUE_PATH = Path(os.environ.get("OPENCLAW_HEAVY_QUEUE_PATH") or (RUNTIME_QUEUE_DIR / "heavy_jobs.jsonl"))


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp(value: dt.datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def enqueue(*, cmd: str, kind: str, priority: int, ttl_minutes: int, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    now = utc_now()
    payload = {
        "schema": 1,
        "id": str(uuid.uuid4()),
        "ts": utc_stamp(now),
        "kind": kind,
        "priority": int(priority),
        "expires_at": utc_stamp(now + dt.timedelta(minutes=max(1, int(ttl_minutes)))),
        "cmd": cmd,
        "meta": meta or {},
        "state": "queued",
    }
    append_jsonl(QUEUE_PATH, payload)
    return payload


def tail_jobs(limit: int) -> list[dict[str, Any]]:
    if not QUEUE_PATH.exists():
        return []
    rows = QUEUE_PATH.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in rows[-max(1, limit) :]:
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Append-only heavy job queue")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enqueue = sub.add_parser("enqueue")
    p_enqueue.add_argument("--cmd", dest="job_cmd", required=True)
    p_enqueue.add_argument("--kind", default="HEAVY_CODE")
    p_enqueue.add_argument("--priority", type=int, default=50)
    p_enqueue.add_argument("--ttl-minutes", type=int, default=720)

    p_tail = sub.add_parser("tail")
    p_tail.add_argument("-n", type=int, default=50)

    args = parser.parse_args()

    if args.cmd == "enqueue":
        item = enqueue(
            cmd=args.job_cmd,
            kind=args.kind,
            priority=args.priority,
            ttl_minutes=args.ttl_minutes,
        )
        print(json.dumps(item, indent=2, sort_keys=True))
        return 0

    if args.cmd == "tail":
        print(json.dumps(tail_jobs(args.n), indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
