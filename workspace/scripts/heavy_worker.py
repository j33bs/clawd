#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from contract_policy import gpu_tool_allowed_now, load_contract  # type: ignore  # noqa: E402

QUEUE_PATH = Path(os.environ.get("OPENCLAW_HEAVY_QUEUE_PATH") or (ROOT / "workspace" / "state_runtime" / "queue" / "heavy_jobs.jsonl"))
RUNS_LOG = Path(os.environ.get("OPENCLAW_HEAVY_RUNS_LOG") or (ROOT / "workspace" / "state_runtime" / "queue" / "heavy_runs.jsonl"))
RUNS_DIR = Path(os.environ.get("OPENCLAW_HEAVY_RUNS_DIR") or (ROOT / "workspace" / "state_runtime" / "queue" / "runs"))
EVENTS_PATH = Path(os.environ.get("OPENCLAW_CONTRACT_EVENTS") or (ROOT / "workspace" / "state_runtime" / "contract" / "events.jsonl"))
CONTRACT_PATH = Path(os.environ.get("OPENCLAW_CONTRACT_CURRENT") or (ROOT / "workspace" / "state_runtime" / "contract" / "current.json"))
GPU_LOCK = ROOT / "workspace" / "scripts" / "gpu_lock.py"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp(value: dt.datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def parse_z(value: Any) -> dt.datetime | None:
    s = str(value or "").strip()
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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def append_event(payload: dict[str, Any]) -> None:
    append_jsonl(EVENTS_PATH, payload)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def seen_job_ids() -> set[str]:
    done: set[str] = set()
    for row in read_jsonl(RUNS_LOG):
        job_id = str(row.get("job_id") or "")
        if not job_id:
            continue
        status = str(row.get("status") or "")
        if status in {"ok", "failed", "expired", "invalid"}:
            done.add(job_id)
    return done


def queued_jobs() -> list[dict[str, Any]]:
    now = utc_now()
    done = seen_job_ids()
    candidates: list[dict[str, Any]] = []
    for index, row in enumerate(read_jsonl(QUEUE_PATH)):
        state = str(row.get("state") or "")
        job_id = str(row.get("id") or "")
        cmd = str(row.get("cmd") or "")
        if state != "queued" or not job_id or not cmd:
            continue
        if job_id in done:
            continue
        expiry = parse_z(row.get("expires_at"))
        if expiry and expiry <= now:
            append_jsonl(
                RUNS_LOG,
                {
                    "schema": 1,
                    "ts": utc_stamp(),
                    "job_id": job_id,
                    "status": "expired",
                    "reason": "job_expired_before_run",
                },
            )
            continue
        row_copy = dict(row)
        row_copy["_line"] = index
        candidates.append(row_copy)

    candidates.sort(key=lambda j: (int(j.get("priority", 50)), str(j.get("ts", "")), int(j.get("_line", 0))))
    return candidates


def claim_gpu_lock() -> tuple[bool, str]:
    if not GPU_LOCK.exists():
        return True, "gpu_lock_missing_allow"
    proc = subprocess.run(
        [str(GPU_LOCK), "claim", "--holder", "heavy_worker", "--reason", "queue_drain", "--ttl-minutes", "60"],
        capture_output=True,
        text=True,
        check=False,
    )
    msg = (proc.stdout or proc.stderr or "").strip()
    return (proc.returncode == 0), msg


def release_gpu_lock() -> None:
    if not GPU_LOCK.exists():
        return
    subprocess.run(
        [str(GPU_LOCK), "release", "--holder", "heavy_worker"],
        capture_output=True,
        text=True,
        check=False,
    )


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    run_id = f"{job['id']}_{uuid.uuid4().hex[:10]}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    started = utc_now()
    proc = subprocess.run(
        str(job["cmd"]),
        shell=True,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    ended = utc_now()

    (run_dir / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")

    result = {
        "schema": 1,
        "job_id": str(job.get("id")),
        "run_id": run_id,
        "status": "ok" if proc.returncode == 0 else "failed",
        "rc": int(proc.returncode),
        "cmd": str(job.get("cmd", "")),
        "ts_start": utc_stamp(started),
        "ts_end": utc_stamp(ended),
        "duration_s": max(0.0, (ended - started).total_seconds()),
        "priority": int(job.get("priority", 50)),
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_jsonl(RUNS_LOG, result)
    return result


def main() -> int:
    contract = load_contract(str(CONTRACT_PATH))
    policy = gpu_tool_allowed_now("heavy_worker", contract)
    if not bool(policy.get("allowed")):
        append_event({"ts": utc_stamp(), "type": "heavy_worker_noop", "reason": policy.get("reason"), "mode": policy.get("mode")})
        print(json.dumps({"ok": True, "action": "noop", "reason": policy.get("reason"), "mode": policy.get("mode")}, indent=2))
        return 0

    jobs = queued_jobs()
    if not jobs:
        append_event({"ts": utc_stamp(), "type": "heavy_worker_noop", "reason": "no_jobs"})
        print(json.dumps({"ok": True, "action": "noop", "reason": "no_jobs"}, indent=2))
        return 0

    acquired, lock_detail = claim_gpu_lock()
    if not acquired:
        append_event({"ts": utc_stamp(), "type": "heavy_worker_noop", "reason": "gpu_lock_held"})
        print(json.dumps({"ok": True, "action": "noop", "reason": "gpu_lock_held", "detail": lock_detail}, indent=2))
        return 0

    job = jobs[0]
    append_event({"ts": utc_stamp(), "type": "heavy_job_start", "job_id": job.get("id"), "priority": job.get("priority")})
    try:
        result = run_job(job)
    finally:
        release_gpu_lock()

    append_event(
        {
            "ts": utc_stamp(),
            "type": "heavy_job_end",
            "job_id": result.get("job_id"),
            "run_id": result.get("run_id"),
            "rc": result.get("rc"),
            "status": result.get("status"),
        }
    )
    print(json.dumps({"ok": True, "action": "ran", "result": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
