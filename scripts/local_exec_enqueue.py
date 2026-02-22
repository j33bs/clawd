#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.local_exec.queue import enqueue_job


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_budgets() -> dict[str, int]:
    return {
        "max_wall_time_sec": 300,
        "max_tool_calls": 10,
        "max_output_bytes": 262144,
        "max_concurrency_slots": 1,
    }


def default_tool_policy(*, allow_subprocess: bool = False) -> dict[str, object]:
    return {
        "allow_network": False,
        "allow_subprocess": allow_subprocess,
        "allowed_tools": [],
    }


def build_demo_job() -> dict:
    return {
        "job_id": "job-demorepoindex01",
        "job_type": "repo_index_task",
        "created_at_utc": utc_now(),
        "payload": {
            "include_globs": ["workspace/**/*.py", "workspace/**/*.md", "scripts/*.py"],
            "exclude_globs": ["**/*.bak.*"],
            "max_files": 200,
            "max_file_bytes": 32768,
            "keywords": ["policy", "router", "audit"],
        },
        "budgets": default_budgets(),
        "tool_policy": default_tool_policy(allow_subprocess=False),
        "meta": {"source": "enqueue-demo"},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enqueue governed local_exec jobs")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--job-file", help="Path to JSON job document")
    parser.add_argument("--demo", action="store_true", help="Enqueue demo repo_index_task")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    if bool(args.job_file) == bool(args.demo):
        raise SystemExit("choose exactly one of --job-file or --demo")

    if args.demo:
        job = build_demo_job()
    else:
        path = Path(args.job_file).resolve()
        job = json.loads(path.read_text(encoding="utf-8"))

    event = enqueue_job(repo_root, job)
    print(json.dumps({"status": "enqueued", "job_id": job["job_id"], "event_ts": event["ts_utc"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
