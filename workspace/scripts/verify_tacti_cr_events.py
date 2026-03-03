#!/usr/bin/env python3
"""Deterministic summary verifier for unified TACTI-CR events."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from tacti_cr.events import DEFAULT_PATH, read_events, summarize_by_type


def _parse_min_count(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"invalid --min-count '{value}' (expected type=n)")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --min-count '{value}' (empty type)")
        try:
            out[key] = int(raw)
        except ValueError as exc:
            raise ValueError(f"invalid --min-count '{value}' (n must be int)") from exc
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and summarize TACTI-CR events")
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="Events JSONL path")
    parser.add_argument("--min-count", action="append", default=[], help="Assertion: event_type=n")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    if not path.exists():
        print("no events")
        return 0

    try:
        _ = list(read_events(path))
        counts = summarize_by_type(path)
    except Exception as exc:
        print(f"malformed events file: {exc}", file=sys.stderr)
        return 2

    print("event_type,count")
    for key in sorted(counts):
        print(f"{key},{counts[key]}")

    try:
        minimums = _parse_min_count(args.min_count)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    failed = []
    for key, need in sorted(minimums.items()):
        have = int(counts.get(key, 0))
        if have < need:
            failed.append((key, need, have))
    if failed:
        for key, need, have in failed:
            print(f"assertion failed: {key} expected>={need} got={have}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
