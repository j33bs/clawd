#!/usr/bin/env python3
"""Automation status helpers for cron/job observability artifacts."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CRON_DIR = Path.home() / ".openclaw" / "cron"
DEFAULT_RUNS_DIR = Path(os.environ.get("OPENCLAW_CRON_RUNS_DIR", DEFAULT_CRON_DIR / "runs"))
DEFAULT_JOBS_FILE = Path(os.environ.get("OPENCLAW_CRON_JOBS_FILE", DEFAULT_CRON_DIR / "jobs.json"))

OK_STATUSES = {"ok", "success", "ran"}
NON_FAILING_STATUSES = OK_STATUSES | {"running"}


def utc_now_ms() -> int:
    return int(time.time() * 1000)


def ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def resolve_repo_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    invalid = 0
    if not path.exists():
        return entries, invalid
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries, invalid


def default_status_artifact(job_key: str) -> Path:
    return REPO_ROOT / "reports" / "automation" / "job_status" / f"{job_key}.json"


def load_jobs_store(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = read_json_file(path)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    return [job for job in jobs if isinstance(job, dict)]


def find_job(jobs: list[dict[str, Any]], job_id: str | None, job_name: str | None) -> dict[str, Any] | None:
    if job_id:
        for job in jobs:
            if str(job.get("id")) == job_id:
                return job
    if job_name:
        want = job_name.strip().lower()
        for job in jobs:
            if str(job.get("name", "")).strip().lower() == want:
                return job
    return None


def resolve_job_id_name(args: argparse.Namespace) -> tuple[str, str | None]:
    job_id = args.job_id
    job_name = args.job_name
    if job_id:
        return job_id, job_name
    jobs = load_jobs_store(resolve_repo_path(args.jobs_file))
    job = find_job(jobs, None, job_name)
    if not job:
        raise SystemExit(f"Unable to resolve job id for name: {job_name}")
    return str(job.get("id")), str(job.get("name")) if job.get("name") else job_name


def cmd_record(args: argparse.Namespace) -> int:
    ts_ms = utc_now_ms()
    artifact = resolve_repo_path(args.artifact) if args.artifact else default_status_artifact(args.job_id)
    payload = {
        "job_id": args.job_id,
        "job_name": args.job_name,
        "status": args.status,
        "error": args.error,
        "summary": args.summary,
        "ts_ms": ts_ms,
        "ts": ms_to_iso(ts_ms),
    }
    write_json(artifact, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if args.status in NON_FAILING_STATUSES else 1


def _latest_run_payload(job_id: str, job_name: str | None, runs_dir: Path) -> dict[str, Any]:
    run_file = runs_dir / f"{job_id}.jsonl"
    entries, invalid_count = read_jsonl(run_file)
    if not entries:
        return {
            "job_id": job_id,
            "job_name": job_name,
            "status": "missing",
            "error": "no-run-log",
            "run_file": str(run_file),
            "invalid_jsonl_lines": invalid_count,
            "ts_ms": utc_now_ms(),
            "ts": ms_to_iso(utc_now_ms()),
        }

    latest = entries[-1]
    run_ms = latest.get("runAtMs") or latest.get("ts")
    next_due_ms = latest.get("nextRunAtMs")
    payload = {
        "job_id": job_id,
        "job_name": job_name,
        "status": latest.get("status", "unknown"),
        "error": latest.get("error"),
        "summary": latest.get("summary"),
        "run_at_ms": run_ms,
        "run_at": ms_to_iso(int(run_ms)) if isinstance(run_ms, (int, float)) else None,
        "next_due_ms": next_due_ms,
        "next_due": ms_to_iso(int(next_due_ms)) if isinstance(next_due_ms, (int, float)) else None,
        "run_file": str(run_file),
        "invalid_jsonl_lines": invalid_count,
        "ts_ms": utc_now_ms(),
        "ts": ms_to_iso(utc_now_ms()),
    }
    return payload


def cmd_latest_run(args: argparse.Namespace) -> int:
    job_id, resolved_name = resolve_job_id_name(args)
    job_name = resolved_name or args.job_name
    payload = _latest_run_payload(job_id, job_name, resolve_repo_path(args.runs_dir))
    artifact = resolve_repo_path(args.artifact) if args.artifact else default_status_artifact(job_id)
    write_json(artifact, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("status") in OK_STATUSES else 1


def cmd_cron_health(args: argparse.Namespace) -> int:
    runs_dir = resolve_repo_path(args.runs_dir)
    jobs_file = resolve_repo_path(args.jobs_file)
    jobs = load_jobs_store(jobs_file)
    job = find_job(jobs, args.job_id, args.job_name)
    if not job:
        raise SystemExit(f"Job not found (id={args.job_id}, name={args.job_name})")

    job_id = str(job.get("id"))
    job_name = str(job.get("name", args.job_name or job_id))
    latest = _latest_run_payload(job_id, job_name, runs_dir)
    last_run_ms_raw = latest.get("run_at_ms")
    last_run_ms = int(last_run_ms_raw) if isinstance(last_run_ms_raw, (int, float)) else None
    age_hours = None
    if last_run_ms is not None:
        age_hours = round((utc_now_ms() - last_run_ms) / (1000 * 60 * 60), 3)
    fired_recently = age_hours is not None and age_hours <= args.max_age_hours
    last_status = str(latest.get("status"))
    pass_flag = fired_recently and last_status in OK_STATUSES

    next_due_ms = None
    state = job.get("state")
    if isinstance(state, dict):
        raw = state.get("nextRunAtMs")
        if isinstance(raw, (int, float)):
            next_due_ms = int(raw)

    payload = {
        "job_id": job_id,
        "job_name": job_name,
        "last_run_ts": latest.get("run_at"),
        "last_run_ts_ms": last_run_ms,
        "last_status": last_status,
        "last_error": latest.get("error"),
        "next_due_ts": ms_to_iso(next_due_ms),
        "next_due_ts_ms": next_due_ms,
        "max_age_hours": args.max_age_hours,
        "age_hours": age_hours,
        "fired_recently": fired_recently,
        "pass": pass_flag,
        "ts_ms": utc_now_ms(),
        "ts": ms_to_iso(utc_now_ms()),
    }
    artifact = resolve_repo_path(args.artifact)
    write_json(artifact, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if pass_flag else 1


def cmd_memory_size_guard(args: argparse.Namespace) -> int:
    memory_file = resolve_repo_path(args.memory_file)
    if not memory_file.exists():
        raise SystemExit(f"memory file not found: {memory_file}")
    line_count = len(memory_file.read_text(encoding="utf-8").splitlines())
    needs_prune = line_count > args.threshold_lines
    try:
        memory_file_label = str(memory_file.relative_to(REPO_ROOT))
    except ValueError:
        memory_file_label = str(memory_file)

    candidates: list[dict[str, Any]] = []
    memory_dir = REPO_ROOT / "memory"
    if memory_dir.exists():
        for path in sorted(memory_dir.glob("*.md")):
            lines = len(path.read_text(encoding="utf-8").splitlines())
            candidates.append({"file": str(path.relative_to(REPO_ROOT)), "line_count": lines})
        candidates.sort(key=lambda item: item["line_count"], reverse=True)
    payload = {
        "memory_file": memory_file_label,
        "line_count": line_count,
        "threshold_lines": args.threshold_lines,
        "needs_prune": needs_prune,
        "prune_reminder": "MEMORY.md exceeded threshold; include prune plan in next daily briefing." if needs_prune else None,
        "suggested_prune_candidates": candidates[: args.max_candidates],
        "ts_ms": utc_now_ms(),
        "ts": ms_to_iso(utc_now_ms()),
    }
    artifact = resolve_repo_path(args.artifact)
    write_json(artifact, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iter_jsonl_files() -> list[Path]:
    files: list[Path] = []
    explicit = [
        REPO_ROOT / "workspace" / "knowledge_base" / "data" / "entities.jsonl",
        REPO_ROOT / "workspace" / "hivemind" / "data" / "units.jsonl",
    ]
    for path in explicit:
        if path.exists():
            files.append(path)
    extra_dir = REPO_ROOT / "workspace" / "hivemind" / "data"
    if extra_dir.exists():
        for path in sorted(extra_dir.glob("*.jsonl")):
            if path not in files:
                files.append(path)
    return files


def cmd_integrity_scan(args: argparse.Namespace) -> int:
    duplicate_ids = 0
    invalid_jsonl_lines = 0
    seen_ids: set[str] = set()
    ttl_total = 0
    ttl_expired = 0
    scanned_files: list[str] = []
    now = datetime.now(timezone.utc)

    for path in iter_jsonl_files():
        scanned_files.append(str(path.relative_to(REPO_ROOT)))
        entries, invalid = read_jsonl(path)
        invalid_jsonl_lines += invalid
        for item in entries:
            item_id = item.get("id")
            if isinstance(item_id, str) and item_id:
                if item_id in seen_ids:
                    duplicate_ids += 1
                else:
                    seen_ids.add(item_id)
            expiry = item.get("expires_at") or item.get("expiry") or item.get("ttl_expires_at")
            if expiry is None and isinstance(item.get("metadata"), dict):
                expiry = item["metadata"].get("expires_at")
            expiry_dt = parse_iso(expiry)
            if expiry_dt is None:
                continue
            ttl_total += 1
            if expiry_dt < now:
                ttl_expired += 1

    ttl_expired_ratio = round(ttl_expired / ttl_total, 4) if ttl_total else 0.0
    pass_flag = (
        duplicate_ids <= args.duplicate_threshold
        and invalid_jsonl_lines <= args.invalid_jsonl_threshold
        and ttl_expired_ratio <= args.ttl_expired_ratio_threshold
    )
    payload = {
        "duplicate_ids": duplicate_ids,
        "invalid_jsonl_lines": invalid_jsonl_lines,
        "ttl_expired_units": ttl_expired,
        "ttl_total_units": ttl_total,
        "ttl_expired_ratio": ttl_expired_ratio,
        "thresholds": {
            "duplicate_ids": args.duplicate_threshold,
            "invalid_jsonl_lines": args.invalid_jsonl_threshold,
            "ttl_expired_ratio": args.ttl_expired_ratio_threshold,
        },
        "pass": pass_flag,
        "scanned_files": scanned_files,
        "ts_ms": utc_now_ms(),
        "ts": ms_to_iso(utc_now_ms()),
    }
    artifact = resolve_repo_path(args.artifact)
    write_json(artifact, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if pass_flag else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automation status helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)

    record = sub.add_parser("record", help="Write a direct job status artifact")
    record.add_argument("--job-id", required=True)
    record.add_argument("--job-name")
    record.add_argument("--status", required=True)
    record.add_argument("--error")
    record.add_argument("--summary")
    record.add_argument("--artifact")
    record.set_defaults(func=cmd_record)

    latest = sub.add_parser("latest-run", help="Write artifact from latest cron run JSONL entry")
    latest.add_argument("--job-id")
    latest.add_argument("--job-name")
    latest.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    latest.add_argument("--jobs-file", default=str(DEFAULT_JOBS_FILE))
    latest.add_argument("--artifact")
    latest.set_defaults(func=cmd_latest_run)

    health = sub.add_parser("cron-health", help="Verify a cron job has fired recently and succeeded")
    health.add_argument("--job-id")
    health.add_argument("--job-name")
    health.add_argument("--max-age-hours", type=float, default=26.0)
    health.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    health.add_argument("--jobs-file", default=str(DEFAULT_JOBS_FILE))
    health.add_argument("--artifact", required=True)
    health.set_defaults(func=cmd_cron_health)

    memory = sub.add_parser("memory-size-guard", help="Guard MEMORY.md size and emit prune hints")
    memory.add_argument("--memory-file", default="MEMORY.md")
    memory.add_argument("--threshold-lines", type=int, default=180)
    memory.add_argument("--max-candidates", type=int, default=5)
    memory.add_argument("--artifact", required=True)
    memory.set_defaults(func=cmd_memory_size_guard)

    integrity = sub.add_parser("integrity-scan", help="Quick integrity scan across JSONL stores")
    integrity.add_argument("--duplicate-threshold", type=int, default=0)
    integrity.add_argument("--invalid-jsonl-threshold", type=int, default=0)
    integrity.add_argument("--ttl-expired-ratio-threshold", type=float, default=0.2)
    integrity.add_argument("--artifact", required=True)
    integrity.set_defaults(func=cmd_integrity_scan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
