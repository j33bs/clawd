#!/usr/bin/env python3
"""TeamChat planner+coder loop with append-only evidence and shared local memory."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

from team_chat_adapters import build_adapters
import subprocess

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from tacti_cr.temporal_watchdog import temporal_reset_event
except Exception:  # pragma: no cover
    temporal_reset_event = None
try:
    from tacti_cr.mirror import update_from_event as mirror_update_from_event
except Exception:  # pragma: no cover
    mirror_update_from_event = None
try:
    from tacti_cr.valence import update_valence as valence_update
except Exception:  # pragma: no cover
    valence_update = None


def auto_commit_changes(repo_root: Path, session_id: str, cycle: int) -> str | None:
    """Auto-commit changes after accepted patch. Returns commit SHA or None."""
    try:
        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        if not result.stdout.strip():
            return None  # No changes to commit
        
        # Stage all changes
        subprocess.run(["git", "add", "-A"], cwd=repo_root, capture_output=True, timeout=30)
        
        # Create commit message
        msg = f"teamchat({session_id}): cycle {cycle} accepted patch"
        
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Get commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return sha_result.stdout.strip()[:8]
    except Exception as e:
        print(f"Auto-commit failed: {e}")
    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_state(path: Path, default_state: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default_state
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = dict(default_state)
            merged.update(data)
            return merged
    except Exception:
        pass
    return default_state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, state: dict[str, Any]) -> None:
    lines = [
        f"# TeamChat Summary {state['session_id']}",
        "",
        f"- updated_at: {utc_now()}",
        f"- mode: {'live' if state.get('live') else 'offline'}",
        f"- status: {state.get('status')}",
        f"- cycles_completed: {state.get('cycle', 0)}",
        f"- accepted_reports: {state.get('accepted_reports', 0)}",
        f"- consecutive_failures: {state.get('consecutive_failures', 0)}",
        f"- queue_depth: {len(state.get('queue', []))}",
        "",
        "## Stop Conditions",
        f"- max_cycles: {state.get('max_cycles')}",
        f"- max_commands_per_cycle: {state.get('max_commands_per_cycle')}",
        f"- max_consecutive_failures: {state.get('max_consecutive_failures')}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def log_event(
    session_path: Path,
    *,
    session_id: str,
    cycle: int,
    actor: str,
    event_type: str,
    data: dict[str, Any],
    route: dict[str, Any] | None = None,
) -> None:
    row = {
        "ts": utc_now(),
        "session_id": session_id,
        "cycle": cycle,
        "actor": actor,
        "event": event_type,
        "data": data,
        "meta": {"route": route or {}},
    }
    append_jsonl(
        session_path,
        row,
    )
    if callable(mirror_update_from_event) and actor not in {"system"}:
        try:
            mirror_update_from_event(actor, row, repo_root=Path(__file__).resolve().parents[2])
        except Exception:
            pass


def check_resumable(state: dict[str, Any]) -> bool:
    """Check if session is resumable (not stopped/accepted/completed)."""
    status = state.get("status", "")
    if status.startswith("stopped:") or status in {"accepted", "request_input"}:
        return False
    return True


def run(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    base_dir = Path(args.output_root) if args.output_root else (repo_root / "workspace" / "teamchat")
    session_id = args.session_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    sessions_file = base_dir / "sessions" / f"{session_id}.jsonl"
    summary_file = base_dir / "summaries" / f"{session_id}.md"
    state_file = base_dir / "state" / f"{session_id}.json"

    # Check for existing session to resume
    resuming = False
    if state_file.exists() and not args.force:
        existing_state = load_state(state_file, {})
        if existing_state.get("session_id") == session_id:
            if check_resumable(existing_state):
                if args.resume or args.task is None:
                    print(f"Resuming session {session_id} (cycle {existing_state.get('cycle', 0)}, status: {existing_state.get('status')})")
                    resuming = True
            elif args.resume:
                print(f"Session {session_id} is not resumable (status: {existing_state.get('status')}). Use --force to start fresh.")
                return 1

    if resuming:
        state = load_state(state_file, {})
        # Override some args if provided
        if args.live is not None:
            state["live"] = bool(args.live)
        if args.max_cycles:
            state["max_cycles"] = int(args.max_cycles)
        if args.max_consecutive_failures:
            state["max_consecutive_failures"] = int(args.max_consecutive_failures)
    else:
        # Defaults for new sessions
        max_cycles = int(args.max_cycles) if args.max_cycles else 3
        max_consecutive_failures = int(args.max_consecutive_failures) if args.max_consecutive_failures else 2
        default_state = {
            "session_id": session_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "live": bool(args.live),
            "task": args.task,
            "status": "running",
            "cycle": 0,
            "queue": [],
            "accepted_reports": 0,
            "consecutive_failures": 0,
            "max_cycles": max_cycles,
            "max_commands_per_cycle": int(args.max_commands_per_cycle),
            "max_consecutive_failures": max_consecutive_failures,
        }
        state = load_state(state_file, default_state)

    # Build adapters (both for new and resumed sessions)
    planner, coder = build_adapters(
        live=bool(state.get("live", False)),
        repo_root=repo_root,
        max_commands_per_cycle=int(args.max_commands_per_cycle),
        extra_allowlist=args.allow_cmd,
    )

    # Log session_start only for new sessions (not resumes)
    if not resuming:
        log_event(
        sessions_file,
        session_id=session_id,
        cycle=int(state["cycle"]),
        actor="system",
        event_type="session_start",
        data={
            "task": args.task,
            "live": bool(args.live),
            "limits": {
                "max_cycles": int(args.max_cycles),
                "max_commands_per_cycle": int(args.max_commands_per_cycle),
                "max_consecutive_failures": int(args.max_consecutive_failures),
            },
        },
        route=None,
    )

    while True:
        if int(state["cycle"]) >= int(state["max_cycles"]):
            state["status"] = "stopped:max_cycles"
            break
        if int(state["consecutive_failures"]) >= int(state["max_consecutive_failures"]):
            state["status"] = "stopped:repeated_failures"
            break

        state["cycle"] = int(state["cycle"]) + 1
        cycle = int(state["cycle"])

        if not state["queue"]:
            task = state.get("task") or args.task
            plan_result = planner.plan(task, state)
            if not plan_result.ok:
                state["consecutive_failures"] = int(state["consecutive_failures"]) + 1
                log_event(
                    sessions_file,
                    session_id=session_id,
                    cycle=cycle,
                    actor="planner",
                    event_type="planner_plan_failed",
                    data={"error": plan_result.error or "unknown"},
                    route=plan_result.route,
                )
                save_state(state_file, state)
                write_summary(summary_file, state)
                continue
            state["queue"] = list(plan_result.data.get("work_orders", []))
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=cycle,
                actor="planner",
                event_type="planner_plan",
                data={"plan": plan_result.data.get("plan", {}), "work_orders": state["queue"]},
                route=plan_result.route,
            )

        if not state["queue"]:
            state["status"] = "stopped:no_work_orders"
            break

        work_order = state["queue"].pop(0)
        log_event(
            sessions_file,
            session_id=session_id,
            cycle=cycle,
            actor="coder",
            event_type="work_order_start",
            data={"work_order": work_order},
            route=None,
        )

        coder_result = coder.execute(work_order, state)
        if not coder_result.ok:
            state["consecutive_failures"] = int(state["consecutive_failures"]) + 1
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=cycle,
                actor="coder",
                event_type="coder_failed",
                data={"error": coder_result.error or "unknown", "work_order_id": work_order.get("id")},
                route=coder_result.route,
            )
            save_state(state_file, state)
            write_summary(summary_file, state)
            continue

        tool_calls = coder_result.data.get("tool_calls", [])
        for row in tool_calls:
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=cycle,
                actor="coder",
                event_type="tool_call",
                data=row,
                route=coder_result.route,
            )

        patch_report = coder_result.data.get("patch_report", {})
        log_event(
            sessions_file,
            session_id=session_id,
            cycle=cycle,
            actor="coder",
            event_type="patch_report",
            data=patch_report,
            route=coder_result.route,
        )

        if callable(temporal_reset_event):
            drift = temporal_reset_event(json.dumps(patch_report, ensure_ascii=True))
            if drift:
                log_event(
                    sessions_file,
                    session_id=session_id,
                    cycle=cycle,
                    actor="system",
                    event_type="temporal_reset",
                    data=drift,
                    route=None,
                )
                state["queue"].insert(
                    0,
                    {
                        "id": f"reanchor-{cycle}",
                        "title": "Temporal re-anchor",
                        "goal": "Re-read today's memory and temporal beacon before continuing",
                        "commands": ["python3 workspace/scripts/temporal_beacon_update.py"],
                        "tests": [],
                        "notes": "Inserted by temporal watchdog",
                    },
                )
                state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
                save_state(state_file, state)
                write_summary(summary_file, state)
                continue

        review_result = planner.review(patch_report, state)
        if not review_result.ok:
            state["consecutive_failures"] = int(state["consecutive_failures"]) + 1
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=cycle,
                actor="planner",
                event_type="planner_review_failed",
                data={"error": review_result.error or "unknown"},
                route=review_result.route,
            )
            save_state(state_file, state)
            write_summary(summary_file, state)
            continue

        decision = str(review_result.data.get("decision") or "revise")
        if decision == "accept":
            state["accepted_reports"] = int(state["accepted_reports"]) + 1
            state["consecutive_failures"] = 0
            state["status"] = "accepted"
            if callable(valence_update):
                valence_update("planner", {"success": True}, repo_root=repo_root)
                valence_update("coder", {"success": True}, repo_root=repo_root)
            
            # Auto-commit changes after acceptance
            commit_sha = auto_commit_changes(repo_root, session_id, state.get("cycle", 0))
            if commit_sha:
                state["last_commit"] = commit_sha
        elif decision == "request_input":
            state["status"] = "request_input"
            state["consecutive_failures"] = 0
            if callable(valence_update):
                valence_update("planner", {"failed": True, "retry_loops": 1}, repo_root=repo_root)
        else:
            next_orders = review_result.data.get("next_work_orders", [])
            if next_orders:
                state["queue"].extend(next_orders)
            state["consecutive_failures"] = int(state["consecutive_failures"]) + 1
            if callable(valence_update):
                valence_update("planner", {"failed": True, "retry_loops": 1}, repo_root=repo_root)
                valence_update("coder", {"failed": True}, repo_root=repo_root)

        log_event(
            sessions_file,
            session_id=session_id,
            cycle=cycle,
            actor="planner",
            event_type="planner_review",
            data={
                "decision": decision,
                "reason": review_result.data.get("reason", ""),
                "next_work_orders": review_result.data.get("next_work_orders", []),
            },
            route=review_result.route,
        )

        save_state(state_file, state)
        write_summary(summary_file, state)

        if state.get("status") in {"accepted", "request_input"}:
            break

    if state.get("status") == "running":
        state["status"] = "stopped:limits"

    save_state(state_file, state)
    write_summary(summary_file, state)
    log_event(
        sessions_file,
        session_id=session_id,
        cycle=int(state["cycle"]),
        actor="system",
        event_type="session_end",
        data={"status": state.get("status")},
        route=None,
    )

    print(json.dumps({
        "session_id": session_id,
        "status": state.get("status"),
        "cycles": state.get("cycle"),
        "paths": {
            "session_jsonl": str(sessions_file),
            "summary_md": str(summary_file),
            "state_json": str(state_file),
        },
    }, ensure_ascii=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TeamChat planner+coder loop")
    parser.add_argument("--task", default=None, help="Top-level task for planner (not needed if resuming)")
    parser.add_argument("--session-id", default="", help="Session id (default: UTC timestamp)")
    parser.add_argument("--output-root", default="", help="Output root (default: workspace/teamchat)")
    parser.add_argument("--max-cycles", type=int, default=0, help="Max cycles (0 = keep existing)")
    parser.add_argument("--max-commands-per-cycle", type=int, default=4)
    parser.add_argument("--max-consecutive-failures", type=int, default=0, help="0 = keep existing")
    parser.add_argument("--allow-cmd", action="append", default=[], help="Extra allowlist regex for live coder commands")
    parser.add_argument("--live", nargs="?", default=None, const=True, help="Enable live adapters (use --live or --live=1)")
    parser.add_argument("--resume", action="store_true", help="Resume existing session if available")
    parser.add_argument("--force", action="store_true", help="Force new session even if one exists")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
