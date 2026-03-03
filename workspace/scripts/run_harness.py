#!/usr/bin/env python3
"""Controlled, resumable autonomous run harness with bounded artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
WORKSPACE_DIR = SCRIPT_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from agent_orchestration import AgentOrchestrator, clamp_timeout
from memory_maintenance import consolidate_memory_fragments, parse_bool, parse_positive_int, run_maintain


DEFAULT_CHECKPOINTS = 6
DEFAULT_INTERVAL_SECONDS = 3600
DEFAULT_ACCELERATED_INTERVAL_SECONDS = 5
DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_BYTES = 200 * 1024 * 1024
DEFAULT_TIMEOUT_STREAK_LIMIT = 3
DEFAULT_RUN_PREFIX = "run_harness"
DEFAULT_VLLM_HEALTH_URL = "http://127.0.0.1:8001/health"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def make_run_id(prefix: str = DEFAULT_RUN_PREFIX) -> str:
    return f"{prefix}_{utc_stamp()}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def safe_git_value(repo_root: Path, args: list[str], default: str = "unknown") -> str:
    try:
        out = subprocess.check_output(["git", "-C", str(repo_root), *args], text=True, stderr=subprocess.DEVNULL)
        value = out.strip()
        return value or default
    except Exception:  # noqa: BLE001
        return default


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip() + "\n")


def redact_env(key: str, value: str) -> str:
    upper = key.upper()
    if any(token in upper for token in ("KEY", "TOKEN", "SECRET", "PASS", "PASSWORD")):
        return "<redacted>"
    return value


def collect_openclaw_env(env: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in sorted(env.keys()):
        if not key.startswith("OPENCLAW_"):
            continue
        out[key] = redact_env(key, str(env[key]))
    return out


def scan_tree_usage(root: Path) -> dict[str, int]:
    file_count = 0
    total_bytes = 0
    if not root.exists():
        return {"file_count": 0, "total_bytes": 0}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        file_count += 1
        try:
            total_bytes += path.stat().st_size
        except OSError:
            continue
    return {"file_count": file_count, "total_bytes": total_bytes}


def exceeds_caps(usage: dict[str, int], max_files: int, max_bytes: int) -> bool:
    return usage["file_count"] > max_files or usage["total_bytes"] > max_bytes


def check_vllm_health(timeout_seconds: float = 1.5) -> bool:
    req = urllib.request.Request(DEFAULT_VLLM_HEALTH_URL, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return int(getattr(resp, "status", 0)) == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def resolve_orchestration_limits(env: Mapping[str, str]) -> tuple[int, int]:
    max_concurrent = parse_positive_int(env.get("OPENCLAW_SUBAGENT_MAX_CONCURRENT"), 4, minimum=1)
    timeout_seconds = parse_positive_int(env.get("OPENCLAW_SESSIONS_SPAWN_TIMEOUT_SECONDS"), 120, minimum=1)
    return max_concurrent, clamp_timeout(timeout_seconds)


def seed_sandbox_repo(repo_root: Path, sandbox_repo: Path) -> None:
    marker = sandbox_repo / ".seeded"
    if marker.exists():
        return
    sandbox_repo.mkdir(parents=True, exist_ok=True)

    source_memory_dir = repo_root / "memory"
    sandbox_memory_dir = sandbox_repo / "memory"
    sandbox_memory_dir.mkdir(parents=True, exist_ok=True)
    if source_memory_dir.exists():
        for path in sorted(source_memory_dir.glob("*.md")):
            if path.is_file():
                shutil.copy2(path, sandbox_memory_dir / path.name)

    source_memory_md = repo_root / "MEMORY.md"
    sandbox_memory_md = sandbox_repo / "MEMORY.md"
    if source_memory_md.exists():
        shutil.copy2(source_memory_md, sandbox_memory_md)
    else:
        sandbox_memory_md.write_text("# MEMORY.md - Long-Term Context\n", encoding="utf-8")

    marker.write_text(utc_now().isoformat().replace("+00:00", "Z") + "\n", encoding="utf-8")


def run_memory_step(sandbox_repo: Path, env: Mapping[str, str]) -> dict:
    today = dt.date.today()
    with_cleanup = parse_bool(env.get("OPENCLAW_MEMORY_CLEANUP"), True)
    with_weekly_distill = parse_bool(env.get("OPENCLAW_MEMORY_WEEKLY_DISTILL"), True)
    with_consolidation = parse_bool(env.get("OPENCLAW_MEMORY_CONSOLIDATE_ON_NIGHTLY"), False)
    retain_days = parse_positive_int(env.get("OPENCLAW_MEMORY_RETAIN_DAYS"), 30, minimum=1)
    archive_prune_days = parse_positive_int(env.get("OPENCLAW_MEMORY_ARCHIVE_PRUNE_DAYS"), 365, minimum=0)

    return run_maintain(
        sandbox_repo,
        today,
        with_snapshot=False,
        with_consolidation=with_consolidation,
        with_weekly_distill=with_weekly_distill,
        with_cleanup=with_cleanup,
        retain_days=retain_days,
        archive_prune_days=archive_prune_days,
    )


def run_heartbeat_step(sandbox_repo: Path) -> dict:
    output_path = sandbox_repo / "workspace" / "state_runtime" / "memory" / "heartbeat_consolidation.json"
    try:
        from heartbeat_enhancer import run_memory_consolidation as heartbeat_run_memory_consolidation

        return heartbeat_run_memory_consolidation(sandbox_repo / "memory", output_path)
    except Exception:  # noqa: BLE001
        return consolidate_memory_fragments(sandbox_repo / "memory", output_path)


def run_orchestration_step(
    run_dir: Path,
    checkpoint_index: int,
    *,
    max_concurrent: int,
    timeout_seconds: int,
    dry_run: bool,
    vllm_healthy: bool,
    forced_timeout_count: int = 0,
) -> dict:
    state_dir = run_dir / "agent_orchestration"
    orchestrator = AgentOrchestrator(
        state_dir=state_dir,
        timeout_default=timeout_seconds,
        max_concurrent=max_concurrent,
    )

    outcomes_dir = run_dir / "outcomes"
    outcomes_dir.mkdir(parents=True, exist_ok=True)

    attempted = max_concurrent
    succeeded = 0
    failed = 0
    timeout_count = 0

    for idx in range(1, attempted + 1):
        outcome_path = outcomes_dir / f"checkpoint_{checkpoint_index:03d}_session_{idx:02d}.md"
        if dry_run:
            status = "noop_dry_run"
            succeeded += 1
        elif not vllm_healthy:
            status = "noop_vllm_down"
            succeeded += 1
        elif idx <= max(0, forced_timeout_count):
            status = "timeout"
            failed += 1
            timeout_count += 1
        else:
            plan = orchestrator.prepare_spawn(
                f"checkpoint {checkpoint_index} session {idx}",
                timeout_seconds=timeout_seconds,
                enqueue_if_busy=False,
                providers=["local-assistant"],
            )
            run_id = orchestrator.register_run_start(
                agent_id="harness",
                provider=str(plan.get("provider", "local-assistant")),
                request={"checkpoint_index": checkpoint_index, "session_index": idx},
            )
            orchestrator.register_run_end(run_id, status="ok")
            status = "ok"
            succeeded += 1

        outcome_path.write_text(
            "\n".join(
                [
                    f"# Harness Outcome: checkpoint {checkpoint_index}, session {idx}",
                    "",
                    f"- status: {status}",
                    f"- timeout_seconds: {timeout_seconds}",
                    f"- created_at: {utc_now().isoformat().replace('+00:00', 'Z')}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "timeouts": timeout_count,
        "degraded_noop": bool((not vllm_healthy) or dry_run),
        "max_concurrent": max_concurrent,
        "timeout_seconds": timeout_seconds,
        "state_dir": str(state_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded autonomous checkpoint harness.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--duration-seconds", type=int, default=0)
    parser.add_argument("--checkpoints", type=int, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--checkpoint-interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--accelerated", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    return parser.parse_args()


def run_harness(args: argparse.Namespace, *, env: Mapping[str, str], sleep_fn: Callable[[float], None] = time.sleep) -> tuple[int, dict]:
    repo_root = Path(args.repo_root).resolve()
    run_id = args.run_id.strip() if args.run_id else make_run_id()
    run_dir = repo_root / "workspace" / "state_runtime" / "runs" / run_id
    checkpoints_dir = run_dir / "checkpoints"
    progress_path = run_dir / "progress.json"
    final_summary_path = run_dir / "final_summary.json"
    sandbox_repo = run_dir / "sandbox_repo"
    audit_note = repo_root / "workspace" / "audit" / f"run_harness_{run_id}.md"
    env_note = repo_root / "workspace" / "audit" / f"run_harness_env_{run_id}.md"

    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    seed_sandbox_repo(repo_root, sandbox_repo)

    interval = max(1, int(args.checkpoint_interval_seconds))
    if args.accelerated:
        accelerated_interval = parse_positive_int(
            env.get("OPENCLAW_RUN_ACCELERATED_INTERVAL_SECONDS"),
            DEFAULT_ACCELERATED_INTERVAL_SECONDS,
            minimum=1,
        )
        interval = min(interval, accelerated_interval)

    requested_checkpoints = max(1, int(args.checkpoints))
    if int(args.duration_seconds or 0) > 0:
        requested_checkpoints = max(1, int(math.ceil(args.duration_seconds / interval)))

    max_files = parse_positive_int(env.get("OPENCLAW_RUN_MAX_FILES"), DEFAULT_MAX_FILES, minimum=1)
    max_bytes = parse_positive_int(env.get("OPENCLAW_RUN_MAX_BYTES"), DEFAULT_MAX_BYTES, minimum=1)
    timeout_streak_limit = parse_positive_int(
        env.get("OPENCLAW_RUN_TIMEOUT_STREAK_LIMIT"),
        DEFAULT_TIMEOUT_STREAK_LIMIT,
        minimum=1,
    )
    force_timeout_count = parse_positive_int(env.get("OPENCLAW_RUN_HARNESS_FORCE_TIMEOUT_COUNT"), 0, minimum=0)

    progress = {
        "run_id": run_id,
        "started_at": utc_now().isoformat().replace("+00:00", "Z"),
        "total_checkpoints": requested_checkpoints,
        "completed_checkpoints": 0,
        "status": "running",
        "kill_switch_events": [],
    }
    if progress_path.exists():
        try:
            loaded = json.loads(progress_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                progress.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
        progress["total_checkpoints"] = max(int(progress.get("total_checkpoints", 0)), requested_checkpoints)
        progress["status"] = "running"

    if not env_note.exists():
        env_payload = {
            "run_id": run_id,
            "generated_at": utc_now().isoformat().replace("+00:00", "Z"),
            "repo_root": str(repo_root),
            "args": vars(args),
            "env": collect_openclaw_env(env),
        }
        env_note.write_text("# Run Harness Env\n\n```json\n" + json.dumps(env_payload, indent=2, ensure_ascii=True) + "\n```\n", encoding="utf-8")

    if not audit_note.exists():
        audit_note.write_text(
            "\n".join(
                [
                    f"# Run Harness Evidence ({run_id})",
                    "",
                    f"- branch: {safe_git_value(repo_root, ['rev-parse', '--abbrev-ref', 'HEAD'])}",
                    f"- sha: {safe_git_value(repo_root, ['rev-parse', 'HEAD'])}",
                    f"- started_at_utc: {utc_now().isoformat().replace('+00:00', 'Z')}",
                    f"- checkpoints: {progress['total_checkpoints']}",
                    f"- interval_seconds: {interval}",
                    f"- dry_run: {bool(args.dry_run)}",
                    "",
                    "## Checkpoints",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    timeout_streak = 0
    completed = int(progress.get("completed_checkpoints", 0))
    kill_switch_events = list(progress.get("kill_switch_events", []))
    exit_code = 0

    for checkpoint_index in range(completed + 1, int(progress["total_checkpoints"]) + 1):
        kill_switch = []
        started_at = utc_now().isoformat().replace("+00:00", "Z")
        usage_before = scan_tree_usage(run_dir)
        if exceeds_caps(usage_before, max_files, max_bytes):
            kill_switch.append("ARTIFACT_CAP_EXCEEDED")

        checkpoint_payload = {
            "checkpoint": checkpoint_index,
            "started_at": started_at,
            "memory": None,
            "heartbeat": None,
            "orchestration": None,
            "artifact_usage_before": usage_before,
            "artifact_usage_after": None,
            "kill_switch_events": kill_switch,
            "status": "ok",
        }

        try:
            if kill_switch:
                checkpoint_payload["status"] = "failed"
                raise RuntimeError("artifact caps exceeded before checkpoint start")

            checkpoint_payload["memory"] = run_memory_step(sandbox_repo, env)
            checkpoint_payload["heartbeat"] = run_heartbeat_step(sandbox_repo)

            max_concurrent, timeout_seconds = resolve_orchestration_limits(env)
            vllm_healthy = False if args.dry_run else check_vllm_health()
            orchestration = run_orchestration_step(
                run_dir,
                checkpoint_index,
                max_concurrent=max_concurrent,
                timeout_seconds=timeout_seconds,
                dry_run=bool(args.dry_run),
                vllm_healthy=vllm_healthy,
                forced_timeout_count=force_timeout_count,
            )
            orchestration["vllm_healthy"] = vllm_healthy
            checkpoint_payload["orchestration"] = orchestration

            if int(orchestration.get("timeouts", 0)) > 0:
                timeout_streak += 1
            else:
                timeout_streak = 0
            if timeout_streak > timeout_streak_limit:
                kill_switch.append("SPAWN_TIMEOUT_STREAK_EXCEEDED")

            usage_after = scan_tree_usage(run_dir)
            checkpoint_payload["artifact_usage_after"] = usage_after
            if exceeds_caps(usage_after, max_files, max_bytes):
                kill_switch.append("ARTIFACT_CAP_EXCEEDED")

            if kill_switch:
                checkpoint_payload["status"] = "failed"
                raise RuntimeError("kill switch triggered")
        except Exception as exc:  # noqa: BLE001
            checkpoint_payload["status"] = "failed"
            checkpoint_payload["error"] = str(exc)
            if "ARTIFACT_CAP_EXCEEDED" not in checkpoint_payload["kill_switch_events"] and "artifact" in str(exc).lower():
                checkpoint_payload["kill_switch_events"].append("ARTIFACT_CAP_EXCEEDED")
            exit_code = 1
        finally:
            checkpoint_path = checkpoints_dir / f"checkpoint_{checkpoint_index:03d}.json"
            write_json(checkpoint_path, checkpoint_payload)
            progress["completed_checkpoints"] = checkpoint_index
            if checkpoint_payload["kill_switch_events"]:
                for event in checkpoint_payload["kill_switch_events"]:
                    kill_switch_events.append(
                        {
                            "checkpoint": checkpoint_index,
                            "event": event,
                            "at": utc_now().isoformat().replace("+00:00", "Z"),
                        }
                    )
            append_line(
                audit_note,
                f"- checkpoint {checkpoint_index}: status={checkpoint_payload['status']} "
                f"timeouts={(checkpoint_payload.get('orchestration') or {}).get('timeouts', 0)} "
                f"kill_switches={','.join(checkpoint_payload['kill_switch_events']) or 'none'}",
            )

            progress["kill_switch_events"] = kill_switch_events
            write_json(progress_path, progress)

        if checkpoint_payload["status"] != "ok":
            break
        if checkpoint_index < int(progress["total_checkpoints"]) and not args.dry_run:
            sleep_fn(interval)

    summary = {
        "run_id": run_id,
        "status": "ok" if exit_code == 0 else "failed",
        "completed_checkpoints": int(progress["completed_checkpoints"]),
        "total_checkpoints": int(progress["total_checkpoints"]),
        "kill_switch_events": kill_switch_events,
        "run_dir": str(run_dir),
        "audit_note": str(audit_note),
        "env_note": str(env_note),
        "artifact_usage": scan_tree_usage(run_dir),
    }
    write_json(final_summary_path, summary)

    progress["status"] = summary["status"]
    progress["finished_at"] = utc_now().isoformat().replace("+00:00", "Z")
    write_json(progress_path, progress)

    append_line(audit_note, "")
    append_line(audit_note, "## Final Summary")
    append_line(audit_note, f"- status: {summary['status']}")
    append_line(audit_note, f"- completed_checkpoints: {summary['completed_checkpoints']}/{summary['total_checkpoints']}")
    append_line(audit_note, f"- kill_switch_events: {len(summary['kill_switch_events'])}")
    append_line(
        audit_note,
        f"- artifact_usage: files={summary['artifact_usage']['file_count']} bytes={summary['artifact_usage']['total_bytes']}",
    )

    return exit_code, summary


def main() -> int:
    args = parse_args()
    exit_code, summary = run_harness(args, env=os.environ)
    print(json.dumps(summary, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
