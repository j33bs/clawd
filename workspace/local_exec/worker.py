from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .budgets import BudgetExceeded, BudgetLimits, BudgetTracker, kill_switch_enabled
from .evidence import append_event, append_worker_event, write_summary
from .queue import claim_next_job, complete_job, fail_job, heartbeat
from .subprocess_harness import SubprocessPolicyError, resolve_repo_path, run_argv
from .validation import validator_mode


class KillSwitchTriggered(RuntimeError):
    pass


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _worker_version(repo_root: Path) -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return "unknown"


def _model_runtime() -> dict[str, str]:
    model_mode = "stub" if os.environ.get("OPENCLAW_LOCAL_EXEC_MODEL_STUB", "1") == "1" else "live"
    api_base = os.environ.get("OPENCLAW_LOCAL_EXEC_API_BASE") or os.environ.get("OPENAI_BASE_URL") or ""
    model_name = os.environ.get("OPENCLAW_LOCAL_EXEC_MODEL", "local-exec-coordinator")
    return {"model_mode": model_mode, "api_base": api_base, "model_name": model_name}


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


def _check_kill_switch(repo_root: Path, *, job_id: str, where: str) -> None:
    if kill_switch_enabled(repo_root):
        raise KillSwitchTriggered(f"kill_switch:{where}")


def _heartbeat_if_due(
    repo_root: Path,
    *,
    job_id: str,
    worker_id: str,
    lease_sec: int,
    last_heartbeat: float,
) -> float:
    now = time.monotonic()
    hb_interval = max(1.0, lease_sec / 2.0)
    if now - last_heartbeat >= hb_interval:
        heartbeat(repo_root, job_id=job_id, worker_id=worker_id, lease_sec=lease_sec)
        append_event(repo_root, job_id, "lease_heartbeat", {"worker_id": worker_id, "lease_sec": lease_sec})
        return now
    return last_heartbeat


def _step_checkpoint(
    repo_root: Path,
    *,
    tracker: BudgetTracker,
    job_id: str,
    worker_id: str,
    lease_sec: int,
    last_heartbeat: float,
    where: str,
) -> float:
    tracker.check_wall_time()
    _check_kill_switch(repo_root, job_id=job_id, where=where)
    return _heartbeat_if_due(
        repo_root,
        job_id=job_id,
        worker_id=worker_id,
        lease_sec=lease_sec,
        last_heartbeat=last_heartbeat,
    )


def _run_repo_index(
    repo_root: Path,
    job: dict[str, Any],
    tracker: BudgetTracker,
    *,
    worker_id: str,
    lease_sec: int,
    last_heartbeat: float,
) -> tuple[dict[str, Any], float]:
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
            last_heartbeat = _step_checkpoint(
                repo_root,
                tracker=tracker,
                job_id=job["job_id"],
                worker_id=worker_id,
                lease_sec=lease_sec,
                last_heartbeat=last_heartbeat,
                where="repo_index_step",
            )
            try:
                p = resolve_repo_path(repo_root, rel, must_exist=True)
            except SubprocessPolicyError as exc:
                append_event(repo_root, job["job_id"], "path_rejected", {"path": rel[:256], "reason": str(exc)})
                continue
            if not p.is_file():
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
    return ({"files_considered": len(selected), "hits_written": hits, "index_jsonl": str(out_jsonl.relative_to(repo_root))}, last_heartbeat)


def _bounded_argv(argv: list[str]) -> list[str]:
    return [part[:256] for part in argv[:64]]


def _run_test_runner(
    repo_root: Path,
    job: dict[str, Any],
    tracker: BudgetTracker,
    *,
    worker_id: str,
    lease_sec: int,
    last_heartbeat: float,
) -> tuple[dict[str, Any], float]:
    _ensure_policy(job, requires_subprocess=True, requires_network=False)
    payload = job["payload"]
    commands = payload.get("commands", [])
    timeout_sec = int(payload.get("timeout_sec", 120))
    env_allow = payload.get("env_allow", [])

    try:
        cwd = resolve_repo_path(repo_root, str(payload.get("cwd", ".")), must_exist=True)
    except SubprocessPolicyError as exc:
        append_event(repo_root, job["job_id"], "path_rejected", {"path": str(payload.get("cwd", "."))[:256], "reason": str(exc)})
        raise RuntimeError(str(exc)) from exc

    results: list[dict[str, Any]] = []
    for argv in commands:
        last_heartbeat = _step_checkpoint(
            repo_root,
            tracker=tracker,
            job_id=job["job_id"],
            worker_id=worker_id,
            lease_sec=lease_sec,
            last_heartbeat=last_heartbeat,
            where="test_runner_before_tool_call",
        )
        tracker.record_tool_call(1)
        append_event(
            repo_root,
            job["job_id"],
            "tool_call",
            {
                "name": "subprocess.run_argv",
                "validated_args": {"argv": _bounded_argv(argv), "cwd": str(cwd.relative_to(repo_root)), "timeout_sec": timeout_sec},
            },
        )
        result = run_argv(
            argv,
            repo_root=repo_root,
            cwd=cwd,
            timeout_sec=timeout_sec,
            env_allowlist=env_allow,
            max_output_bytes=tracker.limits.max_output_bytes,
        )
        tracker.record_output_bytes(len(result.get("stdout", "").encode("utf-8")) + len(result.get("stderr", "").encode("utf-8")))
        append_event(
            repo_root,
            job["job_id"],
            "tool_result",
            {
                "name": "subprocess.run_argv",
                "exit_code": result.get("returncode"),
                "timed_out": bool(result.get("timed_out")),
                "stdout_bytes": int(result.get("stdout_bytes", 0)),
                "stderr_bytes": int(result.get("stderr_bytes", 0)),
                "stdout_truncated": bool(result.get("stdout_truncated", False)),
                "stderr_truncated": bool(result.get("stderr_truncated", False)),
            },
        )
        results.append(result)

    summary_lines = ["# Test Runner Task", "", f"- job_id: {job['job_id']}", f"- commands_run: {len(results)}"]
    for idx, item in enumerate(results, start=1):
        summary_lines.append(f"- cmd_{idx}_rc: {item['returncode']}")
    write_summary(repo_root, job["job_id"], "\n".join(summary_lines) + "\n")
    return ({"commands_run": len(results), "results": results}, last_heartbeat)


def _run_doc_compactor(
    repo_root: Path,
    job: dict[str, Any],
    tracker: BudgetTracker,
    *,
    worker_id: str,
    lease_sec: int,
    last_heartbeat: float,
) -> tuple[dict[str, Any], float]:
    _ensure_policy(job, requires_subprocess=False, requires_network=False)
    payload = job["payload"]
    raw_inputs = payload.get("inputs", [])
    max_input_bytes = int(payload.get("max_input_bytes", 262144))
    max_output_bytes = int(payload.get("max_output_bytes", 65536))
    title = str(payload.get("title", "Doc Compactor"))

    chunks: list[str] = []
    used = 0
    for raw_path in raw_inputs:
        last_heartbeat = _step_checkpoint(
            repo_root,
            tracker=tracker,
            job_id=job["job_id"],
            worker_id=worker_id,
            lease_sec=lease_sec,
            last_heartbeat=last_heartbeat,
            where="doc_compactor_step",
        )
        try:
            path = resolve_repo_path(repo_root, str(raw_path), must_exist=True)
        except SubprocessPolicyError as exc:
            append_event(repo_root, job["job_id"], "path_rejected", {"path": str(raw_path)[:256], "reason": str(exc)})
            continue
        if not path.is_file():
            continue
        raw = path.read_bytes()
        take = min(len(raw), max(0, max_input_bytes - used))
        if take <= 0:
            break
        text = raw[:take].decode("utf-8", errors="replace")
        used += take
        try:
            display_path = path.resolve().relative_to(repo_root.resolve())
        except Exception:
            display_path = path
        chunks.append(f"## {display_path}\n{text[:2000]}")

    # Bounded model request summary; doc compactor currently remains deterministic/offline.
    append_event(
        repo_root,
        job["job_id"],
        "model_request_summary",
        {
            "invoked": False,
            "reason": "doc_compactor_uses_local_compaction",
            "input_count": len(raw_inputs),
            "max_input_bytes": max_input_bytes,
        },
    )

    summary = f"# {title}\n\n" + "\n\n".join(chunks)
    if len(summary.encode("utf-8")) > max_output_bytes:
        summary = summary.encode("utf-8")[:max_output_bytes].decode("utf-8", errors="replace")

    tracker.record_output_bytes(len(summary.encode("utf-8")))
    write_summary(repo_root, job["job_id"], summary)
    return ({"inputs_considered": len(raw_inputs), "bytes_read": used}, last_heartbeat)


def _execute_job(
    repo_root: Path,
    job: dict[str, Any],
    tracker: BudgetTracker,
    *,
    worker_id: str,
    lease_sec: int,
    last_heartbeat: float,
) -> tuple[dict[str, Any], float]:
    job_type = job["job_type"]
    if job_type == "repo_index_task":
        return _run_repo_index(repo_root, job, tracker, worker_id=worker_id, lease_sec=lease_sec, last_heartbeat=last_heartbeat)
    if job_type == "test_runner_task":
        return _run_test_runner(repo_root, job, tracker, worker_id=worker_id, lease_sec=lease_sec, last_heartbeat=last_heartbeat)
    if job_type == "doc_compactor_task":
        return _run_doc_compactor(repo_root, job, tracker, worker_id=worker_id, lease_sec=lease_sec, last_heartbeat=last_heartbeat)
    raise RuntimeError(f"unsupported_job_type:{job_type}")


def _build_run_header(repo_root: Path, job: dict[str, Any], worker_id: str) -> dict[str, Any]:
    model_runtime = _model_runtime()
    return {
        "worker_id": worker_id,
        "worker_version": _worker_version(repo_root),
        "repo_root_resolved": os.path.realpath(str(repo_root)),
        "validator_mode": validator_mode(),
        "model_mode": model_runtime["model_mode"],
        "api_base": model_runtime["api_base"],
        "model_name": model_runtime["model_name"],
        "tool_policy_hash": _stable_hash(job.get("tool_policy", {})),
        "budgets_hash": _stable_hash(job.get("budgets", {})),
    }


def run_once(repo_root: Path, worker_id: str = "local-exec-worker", lease_sec: int = 60) -> dict[str, Any]:
    if kill_switch_enabled(repo_root):
        return {"status": "kill_switch", "error": "kill_switch:before_claim"}

    job = claim_next_job(repo_root, worker_id=worker_id, lease_sec=lease_sec)
    if not job:
        return {"status": "idle"}

    job_id = job["job_id"]
    append_event(repo_root, job_id, "claimed", {"worker_id": worker_id})
    append_event(repo_root, job_id, "run_header", _build_run_header(repo_root, job, worker_id))
    heartbeat(repo_root, job_id=job_id, worker_id=worker_id, lease_sec=lease_sec)
    last_heartbeat = time.monotonic()

    budgets = BudgetLimits(
        max_wall_time_sec=int(job["budgets"]["max_wall_time_sec"]),
        max_tool_calls=int(job["budgets"]["max_tool_calls"]),
        max_output_bytes=int(job["budgets"]["max_output_bytes"]),
        max_concurrency_slots=int(job["budgets"]["max_concurrency_slots"]),
    )
    tracker = BudgetTracker(budgets)

    try:
        result, _last_heartbeat = _execute_job(
            repo_root,
            job,
            tracker,
            worker_id=worker_id,
            lease_sec=lease_sec,
            last_heartbeat=last_heartbeat,
        )
        complete_job(repo_root, job_id=job_id, worker_id=worker_id, result=result)
        append_event(repo_root, job_id, "complete", result)
        return {"status": "complete", "job_id": job_id, "result": result}
    except KillSwitchTriggered as exc:
        fail_job(repo_root, job_id=job_id, worker_id=worker_id, error=str(exc))
        append_event(repo_root, job_id, "failed", {"error": str(exc), "reason_code": "kill_switch"})
        return {"status": "kill_switch", "job_id": job_id, "error": str(exc)}
    except (BudgetExceeded, SubprocessPolicyError, RuntimeError) as exc:
        fail_job(repo_root, job_id=job_id, worker_id=worker_id, error=str(exc))
        append_event(repo_root, job_id, "failed", {"error": str(exc)})
        return {"status": "failed", "job_id": job_id, "error": str(exc)}


def run_loop(
    repo_root: Path,
    worker_id: str,
    lease_sec: int,
    sleep_s: float,
    max_idle_s: int,
) -> None:
    backoff_s = 1.0
    last_idle_emit = time.monotonic()

    while True:
        if kill_switch_enabled(repo_root):
            append_worker_event(repo_root, worker_id, "loop_exit", {"reason": "kill_switch"})
            return

        try:
            outcome = run_once(repo_root=repo_root, worker_id=worker_id, lease_sec=lease_sec)
            backoff_s = 1.0
        except Exception as exc:  # pragma: no cover - transient safeguard
            append_worker_event(
                repo_root,
                worker_id,
                "transient_error",
                {"error": str(exc)[:512], "backoff_s": backoff_s},
            )
            time.sleep(backoff_s)
            backoff_s = min(30.0, backoff_s * 2.0)
            continue

        status = outcome.get("status")
        if status == "kill_switch":
            append_worker_event(repo_root, worker_id, "loop_exit", {"reason": "kill_switch"})
            return

        if status == "idle":
            now = time.monotonic()
            if now - last_idle_emit >= float(max_idle_s):
                append_worker_event(repo_root, worker_id, "idle_heartbeat", {"idle_for_s": int(now - last_idle_emit)})
                last_idle_emit = now
            time.sleep(sleep_s)
        else:
            last_idle_emit = time.monotonic()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw local execution worker")
    parser.add_argument("--repo-root", default=".", help="repo root containing workspace/local_exec")
    parser.add_argument("--worker-id", default="local-exec-worker")
    parser.add_argument("--lease-sec", type=int, default=60)
    parser.add_argument("--sleep-s", type=float, default=2.0)
    parser.add_argument("--max-idle-s", type=int, default=300)
    parser.add_argument("--once", action="store_true", help="process at most one job")
    parser.add_argument("--loop", action="store_true", help="run continuous loop (default if --once is omitted)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.once:
        result = run_once(repo_root=repo_root, worker_id=args.worker_id, lease_sec=args.lease_sec)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    run_loop(
        repo_root=repo_root,
        worker_id=args.worker_id,
        lease_sec=args.lease_sec,
        sleep_s=args.sleep_s,
        max_idle_s=args.max_idle_s,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
