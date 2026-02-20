#!/usr/bin/env python3
"""Verify Novel-10 fixture events against the contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT / "workspace"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from tacti_cr.events import summarize_by_type, read_events
from tacti_cr.novel10_contract import required_for_fixture


def verify_events(path: Path, *, include_ui: bool = False, min_count: int = 1) -> tuple[bool, list[str], dict[str, int]]:
    counts = summarize_by_type(path)
    required = required_for_fixture(repo_root=REPO_ROOT, include_ui=include_ui)
    missing: list[str] = []
    for feature in sorted(required):
        for event_type in required[feature]:
            if int(counts.get(event_type, 0)) < int(min_count):
                missing.append(event_type)
    return (len(missing) == 0), missing, counts


def _print_summary(counts: dict[str, int]) -> None:
    print("event_type,count")
    for key in sorted(counts):
        print(f"{key},{counts[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assert Novel-10 fixture event coverage")
    parser.add_argument("--events-path", default="workspace/state/tacti_cr/events.jsonl")
    parser.add_argument("--include-ui", action="store_true")
    parser.add_argument("--min-count", type=int, default=1)
    args = parser.parse_args()

    path = Path(args.events_path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    if not path.exists():
        print("events file missing", file=sys.stderr)
        return 2

    try:
        _ = list(read_events(path))
    except Exception as exc:
        print(f"malformed events file: {exc}", file=sys.stderr)
        return 2

    ok, missing, counts = verify_events(path, include_ui=bool(args.include_ui), min_count=int(args.min_count))
    _print_summary(counts)
    if ok:
        print("ASSERTIONS: PASS")
        return 0
    print("missing_event_types=" + ",".join(sorted(set(missing))), file=sys.stderr)
    print("ASSERTIONS: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
