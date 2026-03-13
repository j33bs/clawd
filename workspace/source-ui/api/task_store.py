"""File-backed task store for Source UI and Discord bridge tooling."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_UI_ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = SOURCE_UI_ROOT / "state" / "tasks.json"
RUNTIME_SOURCES_PATH = SOURCE_UI_ROOT / "config" / "runtime_task_sources.json"
OPENCLAW_HOME = Path.home() / ".openclaw"
AGENTS_ROOT = OPENCLAW_HOME / "agents"
SUBAGENT_RUNS_PATH = OPENCLAW_HOME / "subagents" / "runs.json"
RUNTIME_LOOKBACK_HOURS = 12
REMOTE_TASK_CACHE_TTL_S = 20.0
REMOTE_TASK_TIMEOUT_S = 0.75
_REMOTE_TASK_CACHE: dict[str, dict[str, Any]] = {}

DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "id": 1001,
        "title": "Stabilize SIM_F risk controls",
        "description": "Investigate why dd_kill is not halting the sim despite deep drawdown.",
        "status": "backlog",
        "priority": "high",
        "assignee": "coder",
        "project": "financial-analysis",
        "origin": "dashboard",
        "created_at": "2026-03-10T00:00:00Z",
    },
    {
        "id": 1002,
        "title": "Finish Discord project bridge",
        "description": "Wire outbound project/task summaries to Discord without making Discord the source of truth.",
        "status": "in_progress",
        "priority": "high",
        "assignee": "coder",
        "project": "source-ui",
        "origin": "dashboard",
        "created_at": "2026-03-10T00:00:00Z",
    },
    {
        "id": 1003,
        "title": "Surface external sentiment feed in dashboard",
        "description": "Display MacBook sentiment feed freshness, resolved model, and source state in Source UI.",
        "status": "done",
        "priority": "medium",
        "assignee": "coder",
        "project": "source-ui",
        "origin": "dashboard",
        "created_at": "2026-03-10T00:00:00Z",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json_atomic(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_epoch_ms(value: Any) -> datetime | None:
    try:
        raw = int(value or 0)
    except Exception:
        return None
    if raw <= 0:
        return None
    return datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _trim(text: str, limit: int = 160) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def _strip_transport_metadata(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = re.sub(r"Conversation info \(untrusted metadata\):\s*```json.*?```", "", value, flags=re.S)
    value = re.sub(r"Sender \(untrusted metadata\):\s*```json.*?```", "", value, flags=re.S)
    return value.strip()


def _slug(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return compact or "node"


def _local_node_id() -> str:
    env_name = str(os.environ.get("OPENCLAW_NODE_ID") or "").strip()
    if env_name:
        return _slug(env_name)
    try:
        completed = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            host_name = str(((payload.get("Self") or {}).get("HostName")) or "").strip()
            if host_name:
                return _slug(host_name)
    except Exception:
        pass
    try:
        return _slug(socket.gethostname())
    except Exception:
        return "local"


def _extract_message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                return str(part["text"])
            if part.get("type") == "input_text" and part.get("input_text"):
                return str(part["input_text"])
    if isinstance(content, str):
        return content
    return ""


def _session_tail_hint(session_log: Path) -> tuple[str | None, str | None]:
    if not session_log.exists() or not session_log.is_file():
        return None, None
    try:
        lines = session_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]
    except Exception:
        return None, None

    task_hint: str | None = None
    user_hint: str | None = None
    assistant_hint: str | None = None

    for raw in lines:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if payload.get("type") != "message":
            continue
        message = payload.get("message")
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip()
        text = _strip_transport_metadata(_extract_message_text(message))
        if not text:
            continue
        if text.startswith("[cron:") or "HEARTBEAT_OK" in text:
            continue
        task_match = re.search(r"(?:\*\*Task\*\*|Task)\s*:\s*(.+)", text, flags=re.I | re.S)
        if task_match:
            task_hint = _trim(task_match.group(1))
        if role == "user" and not user_hint:
            user_hint = _trim(text)
        if role == "assistant":
            assistant_hint = _trim(text)

    return task_hint or user_hint or assistant_hint, assistant_hint or user_hint


def _runtime_status(updated_at: datetime, activity_state: str = "") -> str:
    age_seconds = max(0.0, (_now_utc() - updated_at).total_seconds())
    state = str(activity_state or "").strip().lower()
    if state in {"running", "active", "claimed"}:
        return "in_progress"
    if age_seconds <= 2 * 3600:
        return "in_progress"
    return "review"


def _priority_for_agent(agent_id: str, status: str) -> str:
    if agent_id in {"codex", "claude-code"} or status == "in_progress":
        return "high"
    return "medium"


def _runtime_source_entries(path: Path = RUNTIME_SOURCES_PATH) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    sources: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        source_id = _slug(str(item.get("id") or item.get("label") or url))
        sources.append(
            {
                "id": source_id,
                "label": str(item.get("label") or source_id),
                "url": url,
                "timeout_s": float(item.get("timeout_s") or REMOTE_TASK_TIMEOUT_S),
            }
        )
    return sources


def _with_runtime_identity(
    task: dict[str, Any],
    *,
    node_id: str,
    node_label: str,
    remote_url: str | None = None,
    remote: bool = False,
) -> dict[str, Any]:
    normalized = dict(task)
    base_id = str(normalized.get("id") or "").strip()
    if base_id:
        normalized["id"] = f"runtime:{node_id}:{base_id}" if not base_id.startswith(f"runtime:{node_id}:") else base_id
    normalized["read_only"] = True
    normalized["node_id"] = node_id
    normalized["node_label"] = node_label
    if remote_url:
        normalized["source_url"] = remote_url
    if remote:
        normalized["origin"] = str(normalized.get("origin") or "runtime-remote")
        normalized["runtime_source_label"] = str(normalized.get("runtime_source_label") or "remote runtime")
    return normalized


def load_remote_runtime_tasks(
    *,
    runtime_sources_path: Path = RUNTIME_SOURCES_PATH,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    now = time.monotonic()
    for source in _runtime_source_entries(runtime_sources_path):
        cache_entry = _REMOTE_TASK_CACHE.get(source["id"])
        if cache_entry and (now - float(cache_entry.get("ts") or 0.0)) < REMOTE_TASK_CACHE_TTL_S:
            cached_rows = cache_entry.get("tasks")
            if isinstance(cached_rows, list):
                rows = cached_rows
            else:
                rows = []
        else:
            rows = []
            try:
                with urllib.request.urlopen(source["url"], timeout=source["timeout_s"]) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
                if isinstance(payload, dict):
                    remote_rows = payload.get("tasks")
                else:
                    remote_rows = payload
                if isinstance(remote_rows, list):
                    rows = [row for row in remote_rows if isinstance(row, dict)]
                _REMOTE_TASK_CACHE[source["id"]] = {"ts": now, "tasks": rows}
            except (OSError, TimeoutError, ValueError, json.JSONDecodeError, urllib.error.URLError):
                if cache_entry and isinstance(cache_entry.get("tasks"), list):
                    rows = list(cache_entry["tasks"])
                else:
                    continue
        for row in rows:
            task = _with_runtime_identity(
                row,
                node_id=source["id"],
                node_label=source["label"],
                remote_url=source["url"],
                remote=True,
            )
            task_id = str(task.get("id") or "")
            if not task_id or task_id in seen_ids:
                continue
            seen_ids.add(task_id)
            tasks.append(task)
    tasks.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return tasks


def load_runtime_tasks(
    *,
    agents_root: Path = AGENTS_ROOT,
    subagent_runs_path: Path = SUBAGENT_RUNS_PATH,
    lookback_hours: int = RUNTIME_LOOKBACK_HOURS,
) -> list[dict[str, Any]]:
    now = _now_utc()
    cutoff = now.timestamp() - (max(1, int(lookback_hours)) * 3600)
    tasks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    node_id = _local_node_id()
    node_label = node_id

    for sessions_path in sorted(agents_root.glob("*/sessions/sessions.json")):
        agent_id = sessions_path.parent.parent.name
        payload = _read_json(sessions_path)
        if not isinstance(payload, dict):
            continue

        deduped: dict[str, tuple[str, dict[str, Any]]] = {}
        for session_key, record in payload.items():
            if not isinstance(record, dict):
                continue
            if ":cron:" in session_key:
                continue
            updated_at = _parse_epoch_ms(record.get("updatedAt"))
            if updated_at is None or updated_at.timestamp() < cutoff:
                continue
            session_id = str(record.get("sessionId") or "").strip()
            if not session_id:
                continue
            current = deduped.get(session_id)
            if current is None or len(session_key) < len(current[0]):
                deduped[session_id] = (session_key, record)

        for session_id, (session_key, record) in deduped.items():
            updated_at = _parse_epoch_ms(record.get("updatedAt"))
            if updated_at is None:
                continue
            session_log = sessions_path.parent / f"{session_id}.jsonl"
            title_hint, detail_hint = _session_tail_hint(session_log)
            activity_state = ""
            if isinstance(record.get("acp"), dict):
                activity_state = str(record["acp"].get("state", "")).strip().lower()
            status = _runtime_status(updated_at, activity_state)

            if activity_state == "idle" and not title_hint and agent_id not in {"main", "codex", "claude-code"}:
                continue

            title = title_hint or str(record.get("label") or record.get("title") or f"{agent_id} session")
            description_bits = []
            if detail_hint and detail_hint != title:
                description_bits.append(detail_hint)
            model = str(record.get("model") or record.get("modelProvider") or "").strip()
            if model:
                description_bits.append(model)
            channel = str(record.get("channel") or record.get("lastChannel") or "").strip()
            if channel:
                description_bits.append(f"via {channel}")
            if isinstance(record.get("acp"), dict) and record["acp"].get("cwd"):
                description_bits.append(str(record["acp"]["cwd"]))

            task_id = f"{agent_id}:{session_id}"
            if task_id in seen_ids:
                continue
            seen_ids.add(task_id)
            tasks.append(
                _with_runtime_identity(
                {
                    "id": task_id,
                    "title": title,
                    "description": " | ".join(bit for bit in description_bits if bit),
                    "status": status,
                    "priority": _priority_for_agent(agent_id, status),
                    "assignee": agent_id,
                    "project": "live-runtime",
                    "origin": "runtime-session",
                    "created_at": _iso(updated_at),
                    "updated_at": _iso(updated_at),
                    "read_only": True,
                    "runtime_source": "session",
                    "runtime_source_label": "live session",
                    "session_key": session_key,
                    "session_id": session_id,
                    "channel": record.get("channel") or record.get("lastChannel"),
                    "model": record.get("model"),
                },
                node_id=node_id,
                node_label=node_label,
                )
            )

    subagent_payload = _read_json(subagent_runs_path)
    runs = subagent_payload.get("runs") if isinstance(subagent_payload, dict) else None
    if isinstance(runs, dict):
        for run_id, record in runs.items():
            if not isinstance(record, dict):
                continue
            state = str(record.get("state") or record.get("status") or "").strip().lower()
            if state not in {"running", "active", "queued", "claimed"}:
                continue
            updated_at = _parse_epoch_ms(
                record.get("updatedAt") or record.get("lastActivityAt") or record.get("createdAt")
            ) or now
            title = str(record.get("task") or record.get("title") or record.get("label") or "subagent run").strip()
            if not title:
                title = "subagent run"
            task_id = f"subagent:{run_id}"
            if task_id in seen_ids:
                continue
            seen_ids.add(task_id)
            tasks.append(
                _with_runtime_identity(
                {
                    "id": task_id,
                    "title": _trim(title),
                    "description": _trim(str(record.get("summary") or record.get("cwd") or "")),
                    "status": "in_progress" if state != "queued" else "backlog",
                    "priority": "high",
                    "assignee": str(record.get("agentId") or "subagent"),
                    "project": "live-runtime",
                    "origin": "runtime-subagent",
                    "created_at": _iso(updated_at),
                    "updated_at": _iso(updated_at),
                    "read_only": True,
                    "runtime_source": "subagent",
                    "runtime_source_label": "live subagent",
                    "session_key": record.get("sessionKey"),
                    "session_id": run_id,
                    "channel": None,
                    "model": record.get("model"),
                },
                node_id=node_id,
                node_label=node_label,
                )
            )

    tasks.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return tasks


def load_tasks(path: Path = TASKS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        _write_json_atomic(path, DEFAULT_TASKS)
        return [dict(task) for task in DEFAULT_TASKS]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [dict(task) for task in DEFAULT_TASKS]
    if not isinstance(payload, list):
        return [dict(task) for task in DEFAULT_TASKS]
    return [task for task in payload if isinstance(task, dict)]


def save_tasks(tasks: list[dict[str, Any]], path: Path = TASKS_PATH) -> None:
    _write_json_atomic(path, tasks)


def load_all_tasks(
    path: Path = TASKS_PATH,
    *,
    agents_root: Path = AGENTS_ROOT,
    subagent_runs_path: Path = SUBAGENT_RUNS_PATH,
    runtime_sources_path: Path = RUNTIME_SOURCES_PATH,
    lookback_hours: int = RUNTIME_LOOKBACK_HOURS,
) -> list[dict[str, Any]]:
    local_tasks = load_tasks(path)
    runtime_tasks = load_runtime_tasks(
        agents_root=agents_root,
        subagent_runs_path=subagent_runs_path,
        lookback_hours=lookback_hours,
    )
    remote_runtime_tasks = load_remote_runtime_tasks(runtime_sources_path=runtime_sources_path)
    return [*runtime_tasks, *remote_runtime_tasks, *local_tasks]


def next_task_id(tasks: list[dict[str, Any]]) -> int:
    current = [int(task.get("id", 0)) for task in tasks if str(task.get("id", "")).isdigit()]
    return (max(current) if current else 1000) + 1


def create_task(data: dict[str, Any], path: Path = TASKS_PATH) -> dict[str, Any]:
    tasks = load_tasks(path)
    task = {
        "id": next_task_id(tasks),
        "title": str(data.get("title", "")).strip(),
        "description": str(data.get("description", "")).strip(),
        "status": str(data.get("status", "backlog")).strip() or "backlog",
        "priority": str(data.get("priority", "medium")).strip() or "medium",
        "assignee": str(data.get("assignee", "")).strip(),
        "project": str(data.get("project", "")).strip(),
        "origin": str(data.get("origin", "dashboard")).strip() or "dashboard",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    tasks.append(task)
    save_tasks(tasks, path)
    return task


def update_task(task_id: str, updates: dict[str, Any], path: Path = TASKS_PATH) -> dict[str, Any] | None:
    tasks = load_tasks(path)
    for task in tasks:
        if str(task.get("id")) != str(task_id):
            continue
        task.update({key: value for key, value in updates.items() if value is not None})
        task["updated_at"] = _now_iso()
        save_tasks(tasks, path)
        return task
    return None


def delete_task(task_id: str, path: Path = TASKS_PATH) -> bool:
    tasks = load_tasks(path)
    next_tasks = [task for task in tasks if str(task.get("id")) != str(task_id)]
    if len(next_tasks) == len(tasks):
        return False
    save_tasks(next_tasks, path)
    return True
