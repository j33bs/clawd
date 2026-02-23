#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = REPO_ROOT / "workspace" / "memory" / "wander_log.jsonl"


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        trigger = str(row.get("trigger") or "unknown").strip().lower() or "unknown"
        buckets[trigger].append(row)

    out: dict[str, Any] = {"triggers": {}, "total_rows": len(rows)}
    for trigger in sorted(buckets.keys()):
        data = buckets[trigger]
        scores = [float(item.get("inquiry_momentum_score", 0.0) or 0.0) for item in data]
        exceeds = [bool(item.get("exceeded", False)) for item in data]
        out["triggers"][trigger] = {
            "n": len(scores),
            "mean": round(statistics.fmean(scores), 6) if scores else 0.0,
            "median": round(statistics.median(scores), 6) if scores else 0.0,
            "std": round(statistics.pstdev(scores), 6) if len(scores) > 1 else 0.0,
            "exceed_rate": round((sum(1 for x in exceeds if x) / len(exceeds)), 6) if exceeds else 0.0,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze inquiry momentum grouped by trigger")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = summarize(load_rows(Path(args.log_path)))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

