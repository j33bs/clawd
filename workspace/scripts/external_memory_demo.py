#!/usr/bin/env python3
"""Smoke/demo writer for external memory event store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "workspace"))

from tacti_cr.external_memory import append_event, healthcheck  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write sample events to external memory")
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--event-type", default="smoke")
    parser.add_argument("--payload", default='{"x":1}')
    parser.add_argument("--meta", default="{}")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.payload)
        meta = json.loads(args.meta)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON argument: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("payload must decode to object", file=sys.stderr)
        return 2
    if not isinstance(meta, dict):
        print("meta must decode to object", file=sys.stderr)
        return 2
    if args.n < 1:
        print("--n must be >= 1", file=sys.stderr)
        return 2

    for idx in range(args.n):
        event_payload = dict(payload)
        event_payload["index"] = idx
        append_event(args.event_type, event_payload, meta=meta)

    status = healthcheck()
    print(
        json.dumps(
            {
                "backend": status.get("backend"),
                "path": status.get("path"),
                "last_event_ts": status.get("last_event_ts"),
                "ok": status.get("ok"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

