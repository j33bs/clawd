#!/usr/bin/env python3
"""Dispatch Source mission backlog items into designated runtime main sessions."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASKS_URL = "http://127.0.0.1:18990/api/tasks"
AGENTS_ROOT = Path.home() / ".openclaw" / "agents"
STATE_PATH = REPO_ROOT / "workspace" / "source-ui" / "state" / "backlog_ingest.json"
RESULTS_DIR = REPO_ROOT / "workspace" / "source-ui" / "state" / "backlog_ingest_results"
RUNTIME_AGENT_BY_ASSIGNEE = {
    "dali": "discord-orchestrator",
    "c_lawd": "discord-clawd",
}
REPO_CODING_RUNTIME_AGENT = "codex"
REPO_CODING_TASK_IDS = {
    "source-005",
    "source-006",
    "source-007",
    "source-008",
    "source-009",
}
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
INGEST_LEASE_SECONDS = 20 * 60
INGEST_COOLDOWN_SECONDS = 2 * 60 * 60
REPEAT_SUPPRESSION_SECONDS = 6 * 60 * 60
OUTCOME_MARKERS = {
    "result": "BACKLOG_RESULT:",
    "blocker": "BACKLOG_BLOCKER:",
}
ACP_ERROR_PREFIX = "ACP error (ACP_TURN_FAILED):"


def _read_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _now_ts() -> float:
    return time.time()


def _fetch_tasks(url: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=10.0) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _task_sort_key(task: dict[str, Any]) -> tuple[int, int, str]:
    priority = PRIORITY_ORDER.get(str(task.get("priority") or "").strip().lower(), 99)
    sequence = int(task.get("sequence") or 9999)
    return (priority, sequence, str(task.get("id") or ""))


def _ingest_session_id(runtime_agent: str) -> str:
    return f"source-backlog-{runtime_agent}"


def _ingest_session_key(runtime_agent: str) -> str:
    return f"agent:{runtime_agent}:acp:source-backlog"


def _ingest_session_log(runtime_agent: str) -> Path:
    return AGENTS_ROOT / runtime_agent / "sessions" / f"{_ingest_session_id(runtime_agent)}.jsonl"


def _main_session_key(runtime_agent: str) -> str:
    return f"agent:{runtime_agent}:main"


def _session_record(runtime_agent: str, session_key: str) -> dict[str, Any] | None:
    sessions_path = AGENTS_ROOT / runtime_agent / "sessions" / "sessions.json"
    payload = _read_json(sessions_path)
    if not isinstance(payload, dict):
        return None
    record = payload.get(str(session_key or "").strip())
    return dict(record) if isinstance(record, dict) else None


def _main_session_record(runtime_agent: str) -> dict[str, Any] | None:
    return _session_record(runtime_agent, _main_session_key(runtime_agent))


def _main_session_log(runtime_agent: str) -> Path | None:
    record = _main_session_record(runtime_agent)
    if not isinstance(record, dict):
        return None
    session_file = str(record.get("sessionFile") or "").strip()
    if session_file:
        return Path(session_file)
    session_id = str(record.get("sessionId") or "").strip()
    if session_id:
        return AGENTS_ROOT / runtime_agent / "sessions" / f"{session_id}.jsonl"
    return None


def _parse_gateway_json(stdout: str) -> dict[str, Any] | None:
    text = str(stdout or "").strip()
    if not text:
        return None
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _remove_ingest_session(runtime_agent: str) -> bool:
    sessions_dir = AGENTS_ROOT / runtime_agent / "sessions"
    sessions_path = sessions_dir / "sessions.json"
    payload = _read_json(sessions_path)
    sessions = dict(payload) if isinstance(payload, dict) else {}
    changed = False

    keys_to_remove = []
    for key, record in sessions.items():
        if not isinstance(record, dict):
            continue
        session_id = str(record.get("sessionId") or "").strip()
        if session_id.startswith("source-backlog-"):
            keys_to_remove.append(key)
    for key in keys_to_remove:
        sessions.pop(key, None)
        changed = True

    session_log = _ingest_session_log(runtime_agent)
    if session_log.exists():
        session_log.unlink()
        changed = True

    if changed:
        _write_json(sessions_path, sessions)
    return changed


def _result_path_for_task(task: dict[str, Any]) -> Path:
    task_id = str(task.get("id") or "").strip() or "unknown-task"
    return RESULTS_DIR / f"{task_id}.json"


def _task_prefers_repo_runner(task: dict[str, Any]) -> bool:
    mission_task_id = str(task.get("mission_task_id") or "").strip().lower()
    if mission_task_id in REPO_CODING_TASK_IDS:
        return True
    artifact_path = str(task.get("artifact_path") or "").strip().lower()
    if any(segment in artifact_path for segment in ("/source-ui/", "/workspace/scripts/", "/scripts/")):
        return True
    if artifact_path.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css")):
        return True
    text = " ".join(
        str(task.get(key) or "").strip().lower()
        for key in ("title", "definition_of_done", "status_reason")
    )
    return any(
        needle in text
        for needle in (
            "ui",
            "endpoint",
            "integration",
            "scheduler",
            "harness",
            "distillation",
            "state layer",
            "boundary map",
            "deliberation",
        )
    )


def _repo_coding_session_route(assignee: str) -> dict[str, str]:
    sessions_path = AGENTS_ROOT / REPO_CODING_RUNTIME_AGENT / "sessions" / "sessions.json"
    payload = _read_json(sessions_path)
    if not isinstance(payload, dict):
        raise RuntimeError("repo-capable codex ACP sessions are unavailable")
    preferred_label = f"source-backlog-{assignee}"
    candidates: list[tuple[int, int, int, str, dict[str, Any]]] = []
    for session_key, record in payload.items():
        if not isinstance(record, dict):
            continue
        acp = dict(record.get("acp") or {})
        runtime_options = dict(acp.get("runtimeOptions") or {})
        cwd = str(acp.get("cwd") or runtime_options.get("cwd") or "").strip()
        if cwd != str(REPO_ROOT):
            continue
        if str(acp.get("agent") or "").strip().lower() != REPO_CODING_RUNTIME_AGENT:
            continue
        label = str(record.get("label") or "").strip()
        state = str(acp.get("state") or "").strip().lower()
        updated_at = int(record.get("updatedAt") or 0)
        preference = 0 if label == preferred_label else 1
        state_rank = 0 if state in {"", "idle"} else 1 if state == "running" else 2
        candidates.append((preference, state_rank, -updated_at, str(session_key), record))
    if not candidates:
        raise RuntimeError("no repo-capable codex ACP session is registered under ~/.openclaw/agents/codex")
    _, _, _, session_key, record = sorted(candidates)[0]
    session_file = str(record.get("sessionFile") or "").strip()
    if not session_file:
        session_id = str(record.get("sessionId") or "").strip()
        if session_id:
            session_file = str(AGENTS_ROOT / REPO_CODING_RUNTIME_AGENT / "sessions" / f"{session_id}.jsonl")
    return {
        "runtime_agent": REPO_CODING_RUNTIME_AGENT,
        "session_key": session_key,
        "session_file": session_file,
        "stage_kind": "repo_acp",
    }


def _route_for_task(assignee: str, task: dict[str, Any]) -> dict[str, str]:
    if _task_prefers_repo_runner(task):
        route = _repo_coding_session_route(assignee)
        route["result_path"] = str(_result_path_for_task(task))
        return route
    runtime_agent = RUNTIME_AGENT_BY_ASSIGNEE[assignee]
    return {
        "runtime_agent": runtime_agent,
        "session_key": _main_session_key(runtime_agent),
        "session_file": str(_main_session_log(runtime_agent) or ""),
        "stage_kind": "chat_main",
        "result_path": "",
    }


def _should_bypass_history_suppression(task: dict[str, Any], history_entry: dict[str, Any]) -> bool:
    if not _task_prefers_repo_runner(task):
        return False
    kind = str(history_entry.get("kind") or "").strip().lower()
    detail = str(history_entry.get("detail") or "").strip().lower()
    if kind not in {"blocker", "repeat_suppressed"}:
        return False
    return "spawn subagent" in detail or "sandbox block" in detail


def _dispatch_prompt(task: dict[str, Any], *, route: dict[str, str]) -> str:
    if str(route.get("stage_kind") or "").strip() == "repo_acp":
        result_path = str(route.get("result_path") or "").strip()
        return (
            "Queued Source mission work from Source UI.\n"
            "Runtime route: repo-capable Codex ACP session.\n"
            f"Repo cwd: {REPO_ROOT}\n"
            f"Assigned being: {task.get('assignee')}\n"
            f"Task: {task.get('id')} / {task.get('mission_task_id')} - {task.get('title')}\n"
            f"Reason: {task.get('status_reason')}\n"
            f"Definition of done: {task.get('definition_of_done')}\n"
            "Action: do the next concrete repo-backed step yourself now. Do not stop at analysis only.\n"
            f"After concrete progress or a genuine blocker, write exactly one JSON artifact to {result_path}\n"
            'with keys {"task_id","mission_task_id","kind","text","timestamp"} where kind is "result" or "blocker".\n'
            "Use UTC ISO-8601 for timestamp and keep text concise.\n"
            "If you also reply in chat, end your final reply with exactly one line starting 'BACKLOG_RESULT: ' or 'BACKLOG_BLOCKER: '."
        )
    return (
        "Queued Source mission work from Source UI.\n"
        f"Task: {task.get('id')} / {task.get('mission_task_id')} - {task.get('title')}\n"
        f"Reason: {task.get('status_reason')}\n"
        f"Definition of done: {task.get('definition_of_done')}\n"
        "Action: do the next concrete step yourself now in this real session.\n"
        "Do not reply with acknowledgement only.\n"
        "When concrete progress is produced, end your final reply with exactly one line starting 'BACKLOG_RESULT: '.\n"
        "If you are genuinely blocked, end your final reply with exactly one line starting 'BACKLOG_BLOCKER: '."
    )


def _stage_ingest_session(route: dict[str, str], task: dict[str, Any]) -> dict[str, Any]:
    runtime_agent = str(route.get("runtime_agent") or "").strip()
    session_key = str(route.get("session_key") or "").strip()
    session_record = _session_record(runtime_agent, session_key)
    if not isinstance(session_record, dict):
        raise RuntimeError(f"session missing for {runtime_agent}: {session_key}")
    initial_updated_at = int(session_record.get("updatedAt") or 0)
    result_path = str(route.get("result_path") or "").strip()
    if result_path:
        result_file = Path(result_path)
        result_file.parent.mkdir(parents=True, exist_ok=True)
        if result_file.exists():
            result_file.unlink()

    idempotency_key = (
        f"source-backlog:{runtime_agent}:{str(task.get('id') or '').strip()}:{int(time.time() * 1000)}"
    )
    prompt = _dispatch_prompt(task, route=route)
    payload = {
        "sessionKey": session_key,
        "message": prompt,
        "idempotencyKey": idempotency_key,
    }
    completed = subprocess.run(
        ["openclaw", "gateway", "call", "chat.send", "--json", "--params", json.dumps(payload)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown gateway failure"
        raise RuntimeError(f"chat.send failed for {runtime_agent}: {detail}")
    stdout = completed.stdout.strip()
    response: dict[str, Any] | None = None
    if stdout:
        response = _parse_gateway_json(stdout)
    if response is None:
        refreshed_record = _session_record(runtime_agent, session_key)
        refreshed_updated_at = int((refreshed_record or {}).get("updatedAt") or 0)
        if refreshed_updated_at > initial_updated_at:
            response = {"status": "started", "runId": ""}
        else:
            raise RuntimeError(
                f"chat.send returned invalid JSON for {runtime_agent}: {stdout or 'empty stdout'}"
            )
    if not isinstance(response, dict) or str(response.get("status") or "").strip().lower() not in {"started", "ok"}:
        raise RuntimeError(f"chat.send did not start work for {runtime_agent}: {completed.stdout.strip()}")

    return {
        "runtime_agent": runtime_agent,
        "task_id": str(task.get("id") or ""),
        "mission_task_id": str(task.get("mission_task_id") or ""),
        "title": str(task.get("title") or ""),
        "session_key": session_key,
        "run_id": str(response.get("runId") or ""),
        "idempotency_key": idempotency_key,
        "session_file": str(route.get("session_file") or ""),
        "stage_kind": str(route.get("stage_kind") or "chat_main"),
        "result_path": result_path,
    }


def _parse_iso_timestamp(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _extract_ingest_outcome(runtime_agent: str, *, staged_at: float = 0.0) -> dict[str, Any] | None:
    session_log = _main_session_log(runtime_agent)
    if session_log is None or not session_log.exists() or not session_log.is_file():
        return None
    try:
        lines = session_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
    except Exception:
        return None

    latest: dict[str, Any] | None = None
    for raw in lines:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if payload.get("type") != "message":
            continue
        payload_ts = _parse_iso_timestamp(payload.get("timestamp"))
        if staged_at and payload_ts and payload_ts < staged_at:
            continue
        message = payload.get("message")
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role != "assistant":
            continue
        text = str(message.get("content") or "")
        if isinstance(message.get("content"), list):
            parts = []
            for part in message["content"]:
                if not isinstance(part, dict):
                    continue
                part_text = str(part.get("text") or part.get("input_text") or "").strip()
                if part_text:
                    parts.append(part_text)
            text = "\n".join(parts)
        for line in text.splitlines():
            stripped = line.strip()
            for kind, marker in OUTCOME_MARKERS.items():
                if not stripped.startswith(marker):
                    continue
                latest = {
                    "kind": kind,
                    "text": stripped[len(marker) :].strip(),
                    "timestamp": str(payload.get("timestamp") or ""),
                }
    return latest


def _extract_result_file_outcome(result_path: str, *, task_id: str, staged_at: float = 0.0) -> dict[str, Any] | None:
    path = Path(str(result_path or "").strip())
    if not path.exists() or not path.is_file():
        return None
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return None
    payload_task_id = str(payload.get("task_id") or "").strip()
    if payload_task_id and payload_task_id != str(task_id or "").strip():
        return None
    timestamp = str(payload.get("timestamp") or "").strip()
    payload_ts = _parse_iso_timestamp(timestamp)
    if staged_at > 0.0:
        if payload_ts > 0.0:
            if payload_ts < staged_at:
                return None
        elif path.stat().st_mtime < staged_at:
            return None
    kind = str(payload.get("kind") or "").strip().lower()
    text = str(payload.get("text") or "").strip()
    if kind not in OUTCOME_MARKERS or not text:
        return None
    return {
        "kind": kind,
        "text": text,
        "timestamp": timestamp,
    }


def _resolve_session_log_path(runtime_agent: str, *, session_key: str = "", session_file: str = "") -> Path | None:
    candidate = str(session_file or "").strip()
    if candidate:
        path = Path(candidate)
        if path.exists() and path.is_file():
            return path

    if not session_key:
        return None

    record = _session_record(runtime_agent, session_key)
    if not isinstance(record, dict):
        return None

    candidate = str(record.get("sessionFile") or "").strip()
    if candidate:
        path = Path(candidate)
        if path.exists() and path.is_file():
            return path

    session_id = str(record.get("sessionId") or "").strip()
    if not session_id:
        return None
    path = AGENTS_ROOT / runtime_agent / "sessions" / f"{session_id}.jsonl"
    if path.exists() and path.is_file():
        return path
    return None


def _extract_repo_acp_error_outcome(
    runtime_agent: str,
    *,
    session_key: str = "",
    session_file: str = "",
    staged_at: float = 0.0,
) -> dict[str, Any] | None:
    session_log = _resolve_session_log_path(runtime_agent, session_key=session_key, session_file=session_file)
    if session_log is None:
        return None
    try:
        lines = session_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
    except Exception:
        return None

    latest: dict[str, Any] | None = None
    for raw in lines:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if payload.get("type") != "message":
            continue
        payload_ts = _parse_iso_timestamp(payload.get("timestamp"))
        if staged_at and payload_ts and payload_ts < staged_at:
            continue
        message = payload.get("message")
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip().lower() != "assistant":
            continue
        text = str(message.get("content") or "")
        if isinstance(message.get("content"), list):
            parts = []
            for part in message["content"]:
                if not isinstance(part, dict):
                    continue
                part_text = str(part.get("text") or part.get("input_text") or "").strip()
                if part_text:
                    parts.append(part_text)
            text = "\n".join(parts)
        stripped = text.strip()
        if not stripped.startswith(ACP_ERROR_PREFIX):
            continue
        detail = stripped.splitlines()[0][len(ACP_ERROR_PREFIX) :].strip() or "repo ACP session failed"
        latest = {
            "kind": "blocker",
            "text": detail,
            "timestamp": str(payload.get("timestamp") or ""),
        }
    return latest


def _task_staged_ts(task: dict[str, Any], now_ts: float) -> float:
    for key in ("started_at", "updated_at", "created_at"):
        ts = _parse_iso_timestamp(task.get(key))
        if ts > 0.0:
            return ts
    return now_ts


def _state_outcome_entry(
    *,
    state_entry: dict[str, Any],
    task_id: str,
    runtime_agent: str,
    kind: str,
    text: str,
    now_ts: float,
    timestamp: str = "",
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "runtime_agent": runtime_agent,
        "staged_at": float(state_entry.get("staged_at") or now_ts),
        "cooldown_until": now_ts + INGEST_COOLDOWN_SECONDS,
        "outcome_kind": kind,
        "outcome_text": text.strip(),
        "outcome_at": timestamp.strip(),
        "outcome_seen_ts": now_ts,
    }


def _history_entry(
    task: dict[str, Any],
    *,
    now_ts: float,
    kind: str,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "task_id": str(task.get("id") or ""),
        "assignee": str(task.get("assignee") or ""),
        "status_reason": str(task.get("status_reason") or "").strip(),
        "kind": kind.strip(),
        "detail": detail.strip(),
        "last_seen_ts": now_ts,
        "suppressed_until": now_ts + REPEAT_SUPPRESSION_SECONDS,
    }


def run(tasks_url: str) -> dict[str, Any]:
    cleared_legacy = []
    for runtime_agent in RUNTIME_AGENT_BY_ASSIGNEE.values():
        if _remove_ingest_session(runtime_agent):
            cleared_legacy.append(
                {
                    "runtime_agent": runtime_agent,
                    "reason": "legacy-source-backlog-acp-removed",
                }
            )

    rows = _fetch_tasks(tasks_url)
    mission_rows = [
        row
        for row in rows
        if str(row.get("origin") or "").strip() == "source_mission_config"
        and not str(row.get("id") or "").startswith("runtime:")
    ]
    mission_by_id = {
        str(row.get("id") or "").strip(): row
        for row in mission_rows
        if str(row.get("id") or "").strip()
    }

    active_tasks = {
        str(row.get("assignee") or "").strip(): row
        for row in mission_rows
        if str(row.get("status") or "").strip() in {"in_progress", "review"}
    }
    state_payload = _read_json(STATE_PATH)
    state = dict(state_payload) if isinstance(state_payload, dict) else {}
    history_payload = state.get("_history") if isinstance(state.get("_history"), dict) else {}
    history = dict(history_payload) if isinstance(history_payload, dict) else {}
    next_state: dict[str, Any] = {}
    next_history: dict[str, Any] = {}
    now_ts = _now_ts()

    summary = {
        "tasks_url": tasks_url,
        "staged": [],
        "cleared": cleared_legacy,
        "skipped": [],
        "outcomes": [],
        "suppressed": [],
    }

    for task_id, raw in history.items():
        if not isinstance(raw, dict):
            continue
        suppressed_until = float(raw.get("suppressed_until") or 0.0)
        if suppressed_until > now_ts:
            next_history[str(task_id)] = raw

    for assignee, runtime_agent in RUNTIME_AGENT_BY_ASSIGNEE.items():
        active_task = active_tasks.get(assignee)
        state_entry = state.get(assignee) if isinstance(state.get(assignee), dict) else {}
        staged_task_id = str(state_entry.get("task_id") or "").strip()
        staged_at = float(state_entry.get("staged_at") or 0.0)
        cooldown_until = float(state_entry.get("cooldown_until") or 0.0)
        outcome_kind = str(state_entry.get("outcome_kind") or "").strip()
        staged_task = mission_by_id.get(staged_task_id, {}) if staged_task_id else {}
        route_upgrade_pending = bool(
            staged_task_id
            and isinstance(staged_task, dict)
            and _task_prefers_repo_runner(staged_task)
            and str(state_entry.get("stage_kind") or "").strip() != "repo_acp"
        )
        if not staged_task_id and isinstance(active_task, dict):
            staged_task_id = str(active_task.get("id") or "").strip()
            staged_at = _task_staged_ts(active_task, now_ts)
        staged_task = mission_by_id.get(staged_task_id, {}) if staged_task_id else {}
        result_path = str(state_entry.get("result_path") or "").strip()
        session_key = str(state_entry.get("session_key") or "").strip()
        session_file = str(state_entry.get("session_file") or "").strip()
        stage_kind = str(state_entry.get("stage_kind") or "").strip()
        if result_path:
            outcome = _extract_result_file_outcome(result_path, task_id=staged_task_id, staged_at=staged_at)
            staged_status = str(staged_task.get("status") or "").strip()
            if outcome is None and stage_kind == "repo_acp" and staged_status not in {"review", "done"}:
                outcome = _extract_repo_acp_error_outcome(
                    runtime_agent,
                    session_key=session_key,
                    session_file=session_file,
                    staged_at=staged_at,
                )
        else:
            outcome = _extract_ingest_outcome(runtime_agent, staged_at=staged_at)

        if outcome and staged_task_id:
            _remove_ingest_session(runtime_agent)
            if result_path:
                try:
                    Path(result_path).unlink()
                except FileNotFoundError:
                    pass
            task_row = mission_by_id.get(staged_task_id, {"id": staged_task_id, "assignee": assignee})
            next_state[assignee] = _state_outcome_entry(
                state_entry=state_entry,
                task_id=staged_task_id,
                runtime_agent=runtime_agent,
                kind=str(outcome.get("kind") or "blocker"),
                text=str(outcome.get("text") or "no detail provided"),
                now_ts=now_ts,
                timestamp=str(outcome.get("timestamp") or ""),
            )
            next_history[staged_task_id] = _history_entry(
                task_row,
                now_ts=now_ts,
                kind=str(next_state[assignee]["outcome_kind"] or "blocker"),
                detail=str(next_state[assignee]["outcome_text"] or ""),
            )
            summary["outcomes"].append(
                {
                    "assignee": assignee,
                    "runtime_agent": runtime_agent,
                    "task_id": staged_task_id,
                    "kind": next_state[assignee]["outcome_kind"],
                    "text": next_state[assignee]["outcome_text"],
                }
            )
            continue

        if outcome_kind and now_ts < cooldown_until and not route_upgrade_pending:
            next_state[assignee] = state_entry
            summary["skipped"].append({"assignee": assignee, "runtime_agent": runtime_agent, "reason": "outcome-cooldown"})
            continue

        if active_task and staged_task_id and str(active_task.get("id") or "") == staged_task_id:
            if (now_ts - staged_at) < INGEST_LEASE_SECONDS:
                next_state[assignee] = state_entry
                summary["skipped"].append({"assignee": assignee, "runtime_agent": runtime_agent, "reason": "lease-active"})
                continue
            _remove_ingest_session(runtime_agent)
            task_row = mission_by_id.get(staged_task_id, {"id": staged_task_id, "assignee": assignee})
            next_state[assignee] = _state_outcome_entry(
                state_entry=state_entry,
                task_id=staged_task_id,
                runtime_agent=runtime_agent,
                kind="blocker",
                text="Lease expired before a BACKLOG_RESULT or BACKLOG_BLOCKER artifact was recorded.",
                now_ts=now_ts,
            )
            next_history[staged_task_id] = _history_entry(
                task_row,
                now_ts=now_ts,
                kind="lease_expired",
                detail=str(next_state[assignee]["outcome_text"] or ""),
            )
            summary["outcomes"].append(
                {
                    "assignee": assignee,
                    "runtime_agent": runtime_agent,
                    "task_id": staged_task_id,
                    "kind": "blocker",
                    "text": next_state[assignee]["outcome_text"],
                }
            )
            continue

        if active_task and (not staged_task_id or str(active_task.get("id") or "") != staged_task_id):
            if _remove_ingest_session(runtime_agent):
                summary["cleared"].append({"assignee": assignee, "runtime_agent": runtime_agent, "reason": "other-active"})
            else:
                summary["skipped"].append({"assignee": assignee, "runtime_agent": runtime_agent, "reason": "other-active"})
            continue

        backlog = [
            row
            for row in mission_rows
            if str(row.get("assignee") or "").strip() == assignee
            and str(row.get("status") or "").strip() == "backlog"
        ]
        backlog.sort(key=_task_sort_key)
        eligible = []
        for row in backlog:
            history_entry = next_history.get(str(row.get("id") or "")) or history.get(str(row.get("id") or ""))
            if isinstance(history_entry, dict):
                suppressed_until = float(history_entry.get("suppressed_until") or 0.0)
                if suppressed_until > now_ts and not _should_bypass_history_suppression(row, history_entry):
                    summary["suppressed"].append(
                        {
                            "assignee": assignee,
                            "runtime_agent": runtime_agent,
                            "task_id": str(row.get("id") or ""),
                            "reason": str(history_entry.get("kind") or "repeat"),
                        }
                    )
                    continue
            if staged_task_id and str(row.get("id") or "") == staged_task_id and now_ts < cooldown_until:
                continue
            eligible.append(row)

        if not eligible:
            if _remove_ingest_session(runtime_agent):
                summary["cleared"].append({"assignee": assignee, "runtime_agent": runtime_agent, "reason": "no-eligible-backlog"})
            else:
                summary["skipped"].append({"assignee": assignee, "runtime_agent": runtime_agent, "reason": "no-eligible-backlog"})
            continue

        try:
            route = _route_for_task(assignee, eligible[0])
            staged = _stage_ingest_session(route, eligible[0])
        except RuntimeError as exc:
            summary["skipped"].append(
                {
                    "assignee": assignee,
                    "runtime_agent": runtime_agent,
                    "reason": str(exc),
                }
            )
            continue
        next_state[assignee] = {
            "task_id": staged["task_id"],
            "runtime_agent": staged["runtime_agent"],
            "staged_at": now_ts,
            "cooldown_until": now_ts + INGEST_COOLDOWN_SECONDS,
            "session_key": staged["session_key"],
            "dispatch_run_id": staged["run_id"],
            "idempotency_key": staged["idempotency_key"],
            "session_file": staged["session_file"],
            "stage_kind": staged["stage_kind"],
            "result_path": staged["result_path"],
        }
        summary["staged"].append({"assignee": assignee, **staged})

    state_to_write = dict(next_state)
    if next_history:
        state_to_write["_history"] = next_history
    _write_json(STATE_PATH, state_to_write)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage Source backlog items into runtime ingest sessions")
    parser.add_argument("--tasks-url", default=DEFAULT_TASKS_URL)
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    try:
        summary = run(args.tasks_url)
    except urllib.error.URLError as exc:
        payload = {"error": f"tasks_unreachable: {exc}"}
        print(json.dumps(payload, indent=2))
        return 1

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
