from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .budgets import BudgetExceeded, BudgetLimits, BudgetTracker, kill_switch_enabled
from .evidence import append_event, write_summary
from .queue import claim_next_job, complete_job, fail_job, heartbeat
from .subprocess_harness import SubprocessPolicyError, run_argv


def _read_limited(path: Path, max_bytes: int) -> str:
    data = path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")


def _repo_files(repo_root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _match_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in globs)


def _ensure_policy(job: dict[str, Any], *, requires_subprocess: bool = False, requires_network: bool = False) -> None:
    policy = job.get("tool_policy", {})
    if not isinstance(policy, dict):
        raise RuntimeError("invalid_tool_policy")
    allow_subprocess = bool(policy.get("allow_subprocess", False))
    allow_network = bool(policy.get("allow_network", False))

    if requires_subprocess and not allow_subprocess:
        raise RuntimeError("subprocess_not_allowed")
    if requires_network and not allow_network:
        raise RuntimeError("network_not_allowed")


def _run_repo_index(repo_root: Path, job: dict[str, Any], tracker: BudgetTracker) -> dict[str, Any]:
    _ensure_policy(job, requires_subprocess=False, requires_network=False)
    payload = job["payload"]
    include_globs = payload.get("include_globs", ["*"])
    exclude_globs = payload.get("exclude_globs", [])
    max_files = int(payload.get("max_files", 1000))
    max_file_bytes = int(payload.get("max_file_bytes", 65536))
    keywords = [str(k) for k in payload.get("keywords", [])]

    files = _repo_files(repo_root)
    selected: list[str] = []
    for rel in files:
        if not _match_any(rel, include_globs):
            continue
        if exclude_globs and _match_any(rel, exclude_globs):
            continue
        selected.append(rel)
        if len(selected) >= max_files:
            break

    out_jsonl = repo_root / "workspace" / "local_exec" / "evidence" / f"{job['job_id']}_index.jsonl"
    hits = 0
    with out_jsonl.open("w", encoding="utf-8") as fh:
        for rel in selected:
            tracker.check_wall_time()
            p = repo_root / rel
            if not p.exists() or not p.is_file():
                continue
            text = _read_limited(p, max_file_bytes)
            keyword_hits = [kw for kw in keywords if kw and kw in text]
            if keywords and not keyword_hits:
                continue
            hits += 1
            row = {
                "path": rel,
                "bytes_scanned": min(len(text.encode("utf-8", errors="ignore")), max_file_bytes),
                "keyword_hits": keyword_hits,
            }
            encoded = json.dumps(row, ensure_ascii=False)
            fh.write(encoded + "\n")
            tracker.record_output_bytes(len(encoded) + 1)

    summary = (
        f"# Repo Index Task\n\n"
        f"- job_id: {job['job_id']}\n"
        f"- files_considered: {len(selected)}\n"
        f"- hits_written: {hits}\n"
        f"- output: {out_jsonl.relative_to(repo_root)}\n"
    )
    write_summary(repo_root, job["job_id"], summary)
    return {"files_considered": len(selected), "hits_written": hits, "index_jsonl": str(out_jsonl.relative_to(repo_root))}


def _run_test_runner(repo_root: Path, job: dict[str, Any], tracker: BudgetTracker) -> dict[str, Any]:
    _ensure_policy(job, requires_subprocess=True, requires_network=False)
    payload = job["payload"]
    commands = payload.get("commands", [])
    timeout_sec = int(payload.get("timeout_sec", 120))
    cwd = repo_root / str(payload.get("cwd", "."))
    env_allow = payload.get("env_allow", [])

    results: list[dict[str, Any]] = []
    for argv in commands:
        tracker.check_wall_time()
        tracker.record_tool_call(1)
        result = run_argv(
            argv,
            repo_root=repo_root,
            cwd=cwd,
            timeout_sec=timeout_sec,
            env_allowlist=env_allow,
            max_output_bytes=tracker.limits.max_output_bytes,
        )
        tracker.record_output_bytes(len(result.get("stdout", "").encode("utf-8")) + len(result.get("stderr", "").encode("utf-8")))
        results.append(result)

    summary_lines = ["# Test Runner Task", "", f"- job_id: {job['job_id']}", f"- commands_run: {len(results)}"]
    for idx, item in enumerate(results, start=1):
        summary_lines.append(f"- cmd_{idx}_rc: {item['returncode']}")
    write_summary(repo_root, job["job_id"], "\n".join(summary_lines) + "\n")
    return {"commands_run": len(results), "results": results}


def _run_doc_compactor(repo_root: Path, job: dict[str, Any], tracker: BudgetTracker) -> dict[str, Any]:
    _ensure_policy(job, requires_subprocess=False, requires_network=False)
    payload = job["payload"]
    inputs = [repo_root / str(p) for p in payload.get("inputs", [])]
    max_input_bytes = int(payload.get("max_input_bytes", 262144))
    max_output_bytes = int(payload.get("max_output_bytes", 65536))
    title = str(payload.get("title", "Doc Compactor"))

    chunks: list[str] = []
    used = 0
    for path in inputs:
        tracker.check_wall_time()
        if not path.exists() or not path.is_file():
            continue
        raw = path.read_bytes()
        take = min(len(raw), max(0, max_input_bytes - used))
        if take <= 0:
            break
        text = raw[:take].decode("utf-8", errors="replace")
        used += take
        chunks.append(f"## {path.relative_to(repo_root)}\n{text[:2000]}")

    summary = f"# {title}\n\n" + "\n\n".join(chunks)
    if len(summary.encode("utf-8")) > max_output_bytes:
        summary = summary.encode("utf-8")[:max_output_bytes].decode("utf-8", errors="replace")

    tracker.record_output_bytes(len(summary.encode("utf-8")))
    write_summary(repo_root, job["job_id"], summary)
    return {"inputs_considered": len(inputs), "bytes_read": used}


def _execute_job(repo_root: Path, job: dict[str, Any], tracker: BudgetTracker) -> dict[str, Any]:
    job_type = job["job_type"]
    if job_type == "repo_index_task":
        return _run_repo_index(repo_root, job, tracker)
    if job_type == "test_runner_task":
        return _run_test_runner(repo_root, job, tracker)
    if job_type == "doc_compactor_task":
        return _run_doc_compactor(repo_root, job, tracker)
    raise RuntimeError(f"unsupported_job_type:{job_type}")


def run_once(repo_root: Path, worker_id: str = "local-exec-worker", lease_sec: int = 60) -> dict[str, Any]:
    if kill_switch_enabled(repo_root):
        return {"status": "kill_switch"}

    job = claim_next_job(repo_root, worker_id=worker_id, lease_sec=lease_sec)
    if not job:
        return {"status": "idle"}

    job_id = job["job_id"]
    append_event(repo_root, job_id, "claimed", {"worker_id": worker_id})
    heartbeat(repo_root, job_id=job_id, worker_id=worker_id, lease_sec=lease_sec)

    budgets = BudgetLimits(
        max_wall_time_sec=int(job["budgets"]["max_wall_time_sec"]),
        max_tool_calls=int(job["budgets"]["max_tool_calls"]),
        max_output_bytes=int(job["budgets"]["max_output_bytes"]),
        max_concurrency_slots=int(job["budgets"]["max_concurrency_slots"]),
    )
    tracker = BudgetTracker(budgets)

    try:
        result = _execute_job(repo_root, job, tracker)
        complete_job(repo_root, job_id=job_id, worker_id=worker_id, result=result)
        append_event(repo_root, job_id, "complete", result)
        return {"status": "complete", "job_id": job_id, "result": result}
    except (BudgetExceeded, SubprocessPolicyError, RuntimeError) as exc:
        fail_job(repo_root, job_id=job_id, worker_id=worker_id, error=str(exc))
        append_event(repo_root, job_id, "failed", {"error": str(exc)})
        return {"status": "failed", "job_id": job_id, "error": str(exc)}


def run_loop(repo_root: Path, worker_id: str, lease_sec: int, poll_sec: float) -> None:
    while True:
        outcome = run_once(repo_root=repo_root, worker_id=worker_id, lease_sec=lease_sec)
        if outcome.get("status") in {"idle", "kill_switch"}:
            time.sleep(poll_sec)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw local execution worker")
    parser.add_argument("--repo-root", default=".", help="repo root containing workspace/local_exec")
    parser.add_argument("--worker-id", default="local-exec-worker")
    parser.add_argument("--lease-sec", type=int, default=60)
    parser.add_argument("--poll-sec", type=float, default=2.0)
    parser.add_argument("--once", action="store_true", help="process at most one job")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.once:
        result = run_once(repo_root=repo_root, worker_id=args.worker_id, lease_sec=args.lease_sec)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    run_loop(repo_root=repo_root, worker_id=args.worker_id, lease_sec=args.lease_sec, poll_sec=args.poll_sec)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
