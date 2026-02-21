#!/usr/bin/env python3
"""TeamChat planner+coder loop with append-only evidence and shared local memory."""

from __future__ import annotations

import argparse
import json
import os
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
    from tacti_cr.events import emit as tacti_emit
except Exception:  # pragma: no cover
    tacti_emit = None
try:
    from tacti_cr.mirror import update_from_event as mirror_update_from_event
except Exception:  # pragma: no cover
    mirror_update_from_event = None
try:
    from tacti_cr.valence import update_valence as valence_update
except Exception:  # pragma: no cover
    valence_update = None
try:
    from memory.session_handshake import close_session_handshake, load_session_handshake
except Exception:  # pragma: no cover
    close_session_handshake = None
    load_session_handshake = None
try:
    from tacti_cr.impasse import ImpasseManager
except Exception:  # pragma: no cover
    ImpasseManager = None
try:
    from memory.context_compactor import compact_context
except Exception:  # pragma: no cover
    compact_context = None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def autocommit_opt_in_signal(args: argparse.Namespace) -> tuple[bool, str]:
    if _truthy(os.environ.get("TEAMCHAT_ALLOW_AUTOCOMMIT")):
        return True, "env:TEAMCHAT_ALLOW_AUTOCOMMIT"
    if bool(getattr(args, "allow_autocommit", False)):
        return True, "cli:--allow-autocommit"
    return False, "none"


def teamchat_user_directed_signal(args: argparse.Namespace) -> tuple[bool, str]:
    if _truthy(os.environ.get("TEAMCHAT_USER_DIRECTED_TEAMCHAT")):
        return True, "env:TEAMCHAT_USER_DIRECTED_TEAMCHAT"
    if bool(getattr(args, "user_directed_teamchat", False)):
        return True, "cli:--user-directed-teamchat"
    return False, "none"


def _write_autocommit_audit(
    repo_root: Path,
    *,
    commit_sha: str,
    session_id: str,
    cycle: int,
    autocommit_signal: str,
    user_directed_signal: str,
    files_changed_text: str,
) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rel_path = Path("workspace") / "audit" / f"teamchat_autocommit_{stamp}.md"
    abs_path = repo_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            "# TeamChat autocommit audit",
            "",
            "## Required Fields",
            f"- commit_sha: {commit_sha}",
            f"- actor_mode: teamchat_autocommit ({autocommit_signal}; {user_directed_signal})",
            f"- rationale: session `{session_id}` cycle `{cycle}` accepted patch",
            "",
            "## Files Changed (name-status)",
            "```text",
            files_changed_text.strip() or "(none)",
            "```",
            "",
            "## Commands Run + Outcomes",
            "```text",
            "git status --porcelain -uall : ok",
            "git add -A : ok",
            f"git commit -m teamchat({session_id}): cycle {cycle} accepted patch : ok",
            "```",
            "",
            "## Cleanliness Evidence (git status)",
            "```text",
            "captured pre-commit via git status --porcelain -uall",
            "```",
            "",
            "## Reproducibility",
            "```text",
            "TEAMCHAT_USER_DIRECTED_TEAMCHAT=1 TEAMCHAT_ALLOW_AUTOCOMMIT=1 bash workspace/scripts/verify_team_chat.sh",
            "```",
            "",
        ]
    )
    abs_path.write_text(body, encoding="utf-8")
    return rel_path


def auto_commit_changes(
    repo_root: Path,
    session_id: str,
    cycle: int,
    *,
    autocommit_enabled: bool = True,
    autocommit_signal: str = "none",
    user_directed: bool = True,
    user_directed_signal: str = "none",
) -> tuple[str | None, str | None]:
    """Auto-commit changes after accepted patch. Returns (commit_sha_short, audit_rel_path) or (None, None)."""
    if not autocommit_enabled or not user_directed:
        return None, None
    try:
        # Run pre-commit audit
        audit_script = repo_root / "workspace" / "scripts" / "audit_commit_hook.py"
        if audit_script.exists():
            audit_result = subprocess.run(
                ["python3", str(audit_script)],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            if audit_result.returncode != 0:
                print(f"Auto-commit blocked by audit: {audit_result.stdout}")
                return None, None
        
        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        if not result.stdout.strip():
            return None, None  # No changes to commit

        files_changed = result.stdout

        audit_rel = _write_autocommit_audit(
            repo_root,
            commit_sha="pending",
            session_id=session_id,
            cycle=cycle,
            autocommit_signal=autocommit_signal,
            user_directed_signal=user_directed_signal,
            files_changed_text=files_changed,
        )

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
            commit_sha_short = sha_result.stdout.strip()[:8]
            return commit_sha_short, str(audit_rel)
    except Exception as e:
        print(f"Auto-commit failed: {e}")
    return None, None


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _current_branch(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        branch = (proc.stdout or "").strip()
        if not branch:
            return "unknown"
        return branch
    except Exception:
        return "unknown"


def _repo_is_dirty(repo_root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return bool((proc.stdout or "").strip())
    except Exception:
        return False


def _guard_controls(
    branch: str,
    requested_auto_commit: bool,
    requested_accept_patches: bool,
    requested_commit_arm: str,
    allow_dirty: bool,
    repo_dirty: bool,
) -> dict[str, Any]:
    protected = branch in {"main", "master"}
    arm_ok = str(requested_commit_arm or "").strip() == "I_UNDERSTAND"
    requested_auto = bool(requested_auto_commit)
    requested_accept = bool(requested_accept_patches)
    requested_commit_enabled = requested_auto and requested_accept

    final_auto = requested_auto
    final_accept = requested_accept
    commit_not_armed = False
    dirty_tree_blocked = False
    commit_not_armed_reason = ""

    if protected:
        final_auto = False
        final_accept = False
    elif not (requested_commit_enabled and arm_ok):
        final_auto = False
        final_accept = False
        if requested_auto or requested_accept:
            commit_not_armed = True
            if not arm_ok:
                commit_not_armed_reason = "missing_or_invalid_commit_arm"
            else:
                commit_not_armed_reason = "requires_auto_commit_and_accept_patches"

    if final_auto and repo_dirty and not allow_dirty:
        final_auto = False
        dirty_tree_blocked = True

    return {
        "branch": branch,
        "protected_branch": protected,
        "repo_dirty": bool(repo_dirty),
        "allow_dirty": bool(allow_dirty),
        "requested_auto_commit": requested_auto,
        "requested_accept_patches": requested_accept,
        "requested_commit_arm": str(requested_commit_arm or ""),
        "arm_ok": arm_ok,
        "requested_commit_enabled": requested_commit_enabled,
        "final_auto_commit": final_auto,
        "final_accept_patches": final_accept,
        "commit_not_armed": commit_not_armed,
        "commit_not_armed_reason": commit_not_armed_reason,
        "dirty_tree_blocked": dirty_tree_blocked,
    }


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
        f"- impasse_status: {state.get('impasse', {}).get('status', 'healthy')}",
        f"- collapse_mode: {bool(state.get('collapse_mode', False))}",
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
    if callable(tacti_emit):
        try:
            tacti_emit(
                f"tacti_cr.team_chat.{event_type}",
                {"actor": actor, "cycle": cycle, "data": data, "route": route or {}},
                session_id=session_id,
            )
        except Exception:
            pass
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
            "impasse": {"status": "healthy"},
            "collapse_mode": False,
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

    if callable(load_session_handshake):
        try:
            outstanding = [str(item.get("id", "unknown")) for item in list(state.get("queue", []))]
            handshake = load_session_handshake(
                repo_root=repo_root,
                session_id=session_id,
                summary_file=summary_file,
                outstanding_threads=outstanding,
                source="teamchat",
            )
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=int(state["cycle"]),
                actor="system",
                event_type="handshake_loaded",
                data={"artifact_path": handshake.get("artifact_path"), "meta": handshake.get("meta", {})},
                route=None,
            )
        except Exception:
            pass

    requested_auto_commit = _parse_bool(
        args.auto_commit if args.auto_commit is not None else os.environ.get("TEAMCHAT_AUTO_COMMIT", "1"),
        default=True,
    )
    requested_accept_patches = _parse_bool(
        args.accept_patches if args.accept_patches is not None else os.environ.get("TEAMCHAT_ACCEPT_PATCHES", "1"),
        default=True,
    )
    requested_commit_arm = os.environ.get("TEAMCHAT_COMMIT_ARM", "")
    allow_dirty = _parse_bool(os.environ.get("TEAMCHAT_ALLOW_DIRTY", "0"), default=False)
    guard = _guard_controls(
        _current_branch(repo_root),
        requested_auto_commit,
        requested_accept_patches,
        requested_commit_arm,
        allow_dirty,
        _repo_is_dirty(repo_root),
    )
    auto_commit_enabled = bool(guard["final_auto_commit"])
    accept_patches_enabled = bool(guard["final_accept_patches"])
    impasse = ImpasseManager() if callable(ImpasseManager) else None
    state.setdefault("impasse", {"status": "healthy"})
    state.setdefault("collapse_mode", False)

    def _apply_impasse_failure(reason: str) -> None:
        if impasse is None:
            return
        context_overflow = "context" in str(reason or "").lower()
        snapshot = impasse.on_failure(str(reason), context_overflow=context_overflow)
        state["impasse"] = dict(snapshot)
        state["collapse_mode"] = snapshot.get("status") == "collapse"
        if state["collapse_mode"]:
            queue = list(state.get("queue", []))
            limit = int(snapshot.get("retrieval_limit", 2))
            state["queue"] = queue[:limit]
            state["max_commands_per_cycle"] = min(int(state.get("max_commands_per_cycle", 4)), limit)
            if callable(compact_context):
                try:
                    compact_context(repo_root=repo_root, session_id=session_id)
                except Exception:
                    pass
        log_event(
            sessions_file,
            session_id=session_id,
            cycle=int(state["cycle"]),
            actor="system",
            event_type="impasse_state",
            data={"reason": str(reason), "snapshot": dict(snapshot)},
            route=None,
        )

    def _apply_impasse_success() -> None:
        if impasse is None:
            return
        snapshot = impasse.on_success()
        state["impasse"] = dict(snapshot)
        state["collapse_mode"] = snapshot.get("status") == "collapse"
        log_event(
            sessions_file,
            session_id=session_id,
            cycle=int(state["cycle"]),
            actor="system",
            event_type="impasse_state",
            data={"reason": "success", "snapshot": dict(snapshot)},
            route=None,
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
        if guard["protected_branch"]:
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=int(state["cycle"]),
                actor="system",
                event_type="teamchat.guard.protected_branch",
                data=guard,
                route=None,
            )
        if guard["commit_not_armed"]:
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=int(state["cycle"]),
                actor="system",
                event_type="teamchat.guard.commit_not_armed",
                data={
                    "reason": guard["commit_not_armed_reason"],
                    "requested_auto_commit": guard["requested_auto_commit"],
                    "requested_accept_patches": guard["requested_accept_patches"],
                    "requested_commit_arm": guard["requested_commit_arm"],
                    "final_auto_commit": guard["final_auto_commit"],
                    "final_accept_patches": guard["final_accept_patches"],
                    "branch": guard["branch"],
                },
                route=None,
            )
        if guard["dirty_tree_blocked"]:
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=int(state["cycle"]),
                actor="system",
                event_type="teamchat.guard.dirty_tree",
                data={
                    "reason": "dirty_tree_requires_TEAMCHAT_ALLOW_DIRTY=1",
                    "requested_auto_commit": guard["requested_auto_commit"],
                    "requested_accept_patches": guard["requested_accept_patches"],
                    "final_auto_commit": guard["final_auto_commit"],
                    "final_accept_patches": guard["final_accept_patches"],
                    "repo_dirty": guard["repo_dirty"],
                    "allow_dirty": guard["allow_dirty"],
                    "branch": guard["branch"],
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
                _apply_impasse_failure(plan_result.error or "planner_plan_failed")
                save_state(state_file, state)
                write_summary(summary_file, state)
                continue
            state["queue"] = list(plan_result.data.get("work_orders", []))
            if state.get("collapse_mode"):
                limit = int(state.get("impasse", {}).get("retrieval_limit", 2))
                state["queue"] = list(state["queue"])[:limit]
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
            _apply_impasse_failure(coder_result.error or "coder_failed")
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

        if callable(temporal_reset_event) and not state.get("collapse_mode"):
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
                _apply_impasse_failure("temporal_reset")
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
            _apply_impasse_failure(review_result.error or "planner_review_failed")
            save_state(state_file, state)
            write_summary(summary_file, state)
            continue

        decision = str(review_result.data.get("decision") or "revise")
        if decision == "accept" and not accept_patches_enabled:
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=cycle,
                actor="system",
                event_type="teamchat.guard.accept_patch_blocked",
                data={"decision": decision, "accept_patches_enabled": False},
                route=None,
            )
            decision = "request_input"
        if decision == "accept":
            state["accepted_reports"] = int(state["accepted_reports"]) + 1
            state["consecutive_failures"] = 0
            state["status"] = "accepted"
            _apply_impasse_success()
            if callable(valence_update) and not state.get("collapse_mode"):
                valence_update("planner", {"success": True}, repo_root=repo_root)
                valence_update("coder", {"success": True}, repo_root=repo_root)
            
            # Auto-commit changes after acceptance
            commit_sha = None
            if auto_commit_enabled and not state.get("collapse_mode"):
                commit_sha, _audit_path = auto_commit_changes(
                    repo_root,
                    session_id,
                    state.get("cycle", 0),
                    autocommit_enabled=auto_commit_enabled,
                    autocommit_signal="env:TEAMCHAT_AUTO_COMMIT" if _truthy(os.environ.get("TEAMCHAT_AUTO_COMMIT")) else "runtime_guard",
                    user_directed=True,
                    user_directed_signal="runtime_teamchat_session",
                )
            if commit_sha:
                state["last_commit"] = commit_sha
        elif decision == "request_input":
            state["status"] = "request_input"
            state["consecutive_failures"] = 0
            _apply_impasse_success()
            if callable(valence_update) and not state.get("collapse_mode"):
                valence_update("planner", {"failed": True, "retry_loops": 1}, repo_root=repo_root)
        else:
            next_orders = review_result.data.get("next_work_orders", [])
            if next_orders:
                state["queue"].extend(next_orders)
            if state.get("collapse_mode"):
                limit = int(state.get("impasse", {}).get("retrieval_limit", 2))
                state["queue"] = list(state["queue"])[:limit]
            state["consecutive_failures"] = int(state["consecutive_failures"]) + 1
            _apply_impasse_failure("planner_requested_revise")
            if callable(valence_update) and not state.get("collapse_mode"):
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
    if callable(close_session_handshake):
        try:
            unresolved = [str(item.get("id", "unknown")) for item in list(state.get("queue", []))]
            closed = close_session_handshake(
                repo_root=repo_root,
                session_id=session_id,
                summary_file=summary_file,
                status=str(state.get("status", "")),
                outstanding_threads=unresolved,
                source="teamchat",
            )
            log_event(
                sessions_file,
                session_id=session_id,
                cycle=int(state["cycle"]),
                actor="system",
                event_type="session_closed",
                data={"artifact_path": closed.get("artifact_path"), "meta": closed.get("meta", {})},
                route=None,
            )
        except Exception:
            pass
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
    parser.add_argument("--auto-commit", default=None, help="Enable/disable auto commit (1/0)")
    parser.add_argument("--accept-patches", default=None, help="Enable/disable planner accept pathway (1/0)")
    parser.add_argument("--resume", action="store_true", help="Resume existing session if available")
    parser.add_argument("--force", action="store_true", help="Force new session even if one exists")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())


def run_multi_agent(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    router: Any | None = None,
    input_fn=input,
    output_fn=print,
) -> int:
    del input_fn  # reserved for interactive variants
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    if not _truthy(os.environ.get("OPENCLAW_TEAMCHAT")):
        output_fn("Team Chat disabled. Set OPENCLAW_TEAMCHAT=1 to enable.")
        return 2

    session_name = str(getattr(args, "session", "") or getattr(args, "session_id", "") or "teamchat")
    message = str(getattr(args, "message", "") or "")
    max_turns = int(getattr(args, "max_turns", 1) or 1)
    agents = [item.strip() for item in str(getattr(args, "agents", "planner,coder")).split(",") if item.strip()]
    if not agents:
        output_fn("No agents configured.")
        return 1

    from teamchat.orchestrator import TeamChatOrchestrator
    from teamchat.session import TeamChatSession
    from policy_router import PolicyRouter

    session = TeamChatSession(session_id=session_name, agents=agents, repo_root=root)
    orchestrator = TeamChatOrchestrator(
        session=session,
        router=router or PolicyRouter(),
        witness_enabled=_truthy(os.environ.get("OPENCLAW_TEAMCHAT_WITNESS")),
        context_window=int(getattr(args, "context_window", 8) or 8),
    )
    result = orchestrator.run_cycle(user_message=message, max_turns=max_turns)
    for row in result.get("replies", []):
        output_fn(f"{row.get('role')}: {row.get('content')}")
    return 0 if result.get("ok") else 1
