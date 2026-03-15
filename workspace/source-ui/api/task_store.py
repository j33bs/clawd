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
REPO_ROOT = SOURCE_UI_ROOT.parents[1]
TASKS_PATH = SOURCE_UI_ROOT / "state" / "tasks.json"
RUNTIME_SOURCES_PATH = SOURCE_UI_ROOT / "config" / "runtime_task_sources.json"
SOURCE_MISSION_CONFIG_PATH = SOURCE_UI_ROOT / "config" / "source_mission.json"
BACKLOG_INGEST_STATE_PATH = SOURCE_UI_ROOT / "state" / "backlog_ingest.json"
COMMAND_HISTORY_PATH = SOURCE_UI_ROOT / "state" / "command_history.json"
COMMAND_RECEIPTS_PATH = SOURCE_UI_ROOT / "state" / "command_receipts.json"
APP_PY_PATH = SOURCE_UI_ROOT / "app.py"
PORTFOLIO_API_PATH = SOURCE_UI_ROOT / "api" / "portfolio.py"
DISCORD_BOT_SUPPORT_PATH = SOURCE_UI_ROOT / "api" / "discord_bot_support.py"
DISCORD_BRIDGE_API_PATH = SOURCE_UI_ROOT / "api" / "discord_bridge.py"
BOUNDARY_STATE_API_PATH = SOURCE_UI_ROOT / "api" / "boundary_state.py"
USER_INFERENCE_API_PATH = SOURCE_UI_ROOT / "api" / "user_inference.py"
STATIC_APP_JS_PATH = SOURCE_UI_ROOT / "static" / "js" / "app.js"
STATIC_COMPONENTS_JS_PATH = SOURCE_UI_ROOT / "static" / "js" / "components.js"
STATIC_INDEX_PATH = SOURCE_UI_ROOT / "static" / "index.html"
STATIC_CSS_PATH = SOURCE_UI_ROOT / "static" / "css" / "styles.css"
AGENT_INTEGRATION_DOC_PATH = SOURCE_UI_ROOT / "docs" / "AGENT_INTEGRATION.md"
MODEL_PROMPT_HARNESSES_PATH = SOURCE_UI_ROOT / "config" / "model_prompt_harnesses.json"
TEAMCHAT_ROOT = REPO_ROOT / "workspace" / "teamchat"
DISCORD_MESSAGES_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "discord_messages.jsonl"
DISCORD_RESEARCH_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "discord_research_messages.jsonl"
DISCORD_BOT_SCRIPT_PATH = REPO_ROOT / "workspace" / "scripts" / "discord_bot.py"
USER_INFERENCES_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "user_inferences.jsonl"
PREFERENCE_PROFILE_PATH = REPO_ROOT / "workspace" / "knowledge_base" / "data" / "preference_profile.json"
PAUSE_CHECK_LOG_PATH = REPO_ROOT / "workspace" / "state" / "pause_check_log.jsonl"
PHI_METRICS_PATH = REPO_ROOT / "workspace" / "governance" / "phi_metrics.md"
OPENCLAW_HOME = Path.home() / ".openclaw"
AGENTS_ROOT = OPENCLAW_HOME / "agents"
SUBAGENT_RUNS_PATH = OPENCLAW_HOME / "subagents" / "runs.json"
RUNTIME_LOOKBACK_HOURS = 12
REMOTE_TASK_CACHE_TTL_S = 20.0
REMOTE_TASK_TIMEOUT_S = 0.75
_REMOTE_TASK_CACHE: dict[str, dict[str, Any]] = {}
_REVIEW_CHECK_CACHE: dict[str, dict[str, Any]] = {}
_GIT_COMMIT_EXISTS_CACHE: dict[str, bool] = {}
ORCHESTRATOR_CHANNEL_ID = 1480814946479636574
AIN_PHI_URL = "http://127.0.0.1:18991/api/ain/phi"
AUTO_REVIEW_SETTLE_SECONDS = 8.0
SOURCE_MISSION_INGEST_LEASE_SECONDS = 20 * 60

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


RESEARCH_PROMOTION_ORIGIN = "research_distill"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json_atomic(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, int(limit)) :]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


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


def _normalize_task_kind(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return "experiment" if raw == "experiment" else "task"


def _normalize_source_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value[:6]:
        if isinstance(item, str):
            href = str(item).strip()
            if not href:
                continue
            rows.append(
                {
                    "id": _slug(href),
                    "label": _trim(href, limit=80),
                    "href": href,
                    "ref": href,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        href = str(item.get("href") or item.get("url") or "").strip()
        ref = str(item.get("ref") or "").strip()
        item_id = str(item.get("id") or ref or href or "").strip()
        label = str(item.get("label") or item.get("title") or ref or href or "").strip()
        if not (item_id or label or href or ref):
            continue
        rows.append(
            {
                "id": item_id or _slug(label or href or ref),
                "label": _trim(label or ref or href, limit=80),
                "href": href,
                "ref": ref,
            }
        )
    return rows


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
    return "backlog"


def _runtime_fix_instructions(
    *,
    assignee: str = "",
    updated_at: datetime | None = None,
    reason: str = "",
    runtime_source_label: str = "",
) -> str:
    agent = str(assignee or "assigned lane").strip() or "assigned lane"
    source = str(runtime_source_label or "runtime").strip() or "runtime"
    if reason:
        detail = reason
    else:
        if updated_at is None:
            detail = f"{agent} is not emitting active progress from {source}."
        else:
            age_seconds = max(0.0, (_now_utc() - updated_at).total_seconds())
            age_minutes = max(1, int(age_seconds // 60))
            detail = f"{agent} has not emitted active progress from {source} for {age_minutes} minutes."
    return f"Fix required: {detail} Resume the task with a concrete work update or archive the stale runtime session."


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
            raw_status = str(task.get("status") or "").strip().lower().replace("-", "_").replace(" ", "_")
            if raw_status == "review":
                task["status"] = "backlog"
                task["progress"] = 0
                task["fix_instructions"] = _runtime_fix_instructions(
                    assignee=str(task.get("assignee") or ""),
                    reason=str(task.get("review_status_reason") or task.get("status_reason") or "").strip(),
                    runtime_source_label=str(task.get("runtime_source_label") or source["label"]),
                )
                task.pop("review_requested_at", None)
                task.pop("reviewed_by", None)
                task.pop("reviewed_at", None)
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
                        **(
                            {
                                "fix_instructions": _runtime_fix_instructions(
                                    assignee=agent_id,
                                    updated_at=updated_at,
                                    runtime_source_label="live session",
                                )
                            }
                            if status == "backlog"
                            else {}
                        ),
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



STATUS_ALIASES = {
    "todo": "backlog",
    "queued": "backlog",
    "in-progress": "in_progress",
    "in_progress": "in_progress",
    "in progress": "in_progress",
    "doing": "in_progress",
    "complete": "done",
    "completed": "done",
}

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SOURCE_MISSION_PROGRESS = {
    "backlog": 0,
    "in_progress": 55,
    "review": 90,
    "done": 100,
}
REVIEWER_BY_ASSIGNEE = {
    "dali": "c_lawd",
    "c_lawd": "dali",
    "chatgpt": "c_lawd",
    "codex": "c_lawd",
    "claude-code": "c_lawd",
    "coder": "c_lawd",
    "planner": "c_lawd",
}
SOURCE_MISSION_ASSIGNEE_BY_ID = {
    "source-001": "dali",
    "source-002": "dali",
    "source-003": "c_lawd",
    "source-004": "c_lawd",
    "source-005": "c_lawd",
    "source-006": "dali",
    "source-007": "dali",
    "source-008": "c_lawd",
    "source-009": "dali",
    "source-010": "dali",
}
SOURCE_MISSION_ASSIGNEE_BY_PILLAR = {
    "remember": "c_lawd",
    "feel": "c_lawd",
    "think": "dali",
    "coordinate": "dali",
    "evolve": "dali",
}
SOURCE_MISSION_RUNTIME_ALIASES = {
    "dali": {"dali", "discord-orchestrator"},
    "c_lawd": {"c_lawd", "discord-clawd"},
}
SOURCE_MISSION_CLAIM_LOOKBACK_MINUTES = 30
MISSION_CLAIM_TERM_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "what",
    "when",
    "where",
    "there",
    "layer",
    "loop",
}


def _normalize_task_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "backlog"
    return STATUS_ALIASES.get(raw, raw.replace("-", "_").replace(" ", "_"))


def _normalize_task_priority(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in PRIORITY_ORDER else "medium"


def _coerce_progress(value: Any) -> int | None:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return None


def _parse_iso_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _cached_probe(key: str, ttl_s: float, loader: Any) -> Any:
    now = time.monotonic()
    entry = _REVIEW_CHECK_CACHE.get(key)
    if entry and (now - float(entry.get("ts") or 0.0)) < max(0.1, float(ttl_s)):
        return entry.get("value")
    value = loader()
    _REVIEW_CHECK_CACHE[key] = {"ts": now, "value": value}
    return value


def _git_commit_exists(commit: str) -> bool:
    ref = str(commit or "").strip()
    if not ref:
        return False
    cached = _GIT_COMMIT_EXISTS_CACHE.get(ref)
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(
            ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        ok = completed.returncode == 0
    except Exception:
        ok = False
    _GIT_COMMIT_EXISTS_CACHE[ref] = ok
    return ok


def _service_is_active(unit: str) -> bool:
    service = str(unit or "").strip()
    if not service:
        return False

    def _load() -> bool:
        try:
            completed = subprocess.run(
                ["systemctl", "--user", "is-active", service],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            return completed.returncode == 0 and completed.stdout.strip() == "active"
        except Exception:
            return False

    return bool(_cached_probe(f"service:{service}", 5.0, _load))


def _json_url_ok(url: str, *, ttl_s: float = 5.0) -> bool:
    target = str(url or "").strip()
    if not target:
        return False

    def _load() -> bool:
        try:
            with urllib.request.urlopen(target, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return isinstance(payload, dict) and bool(payload.get("ok", False))
        except Exception:
            return False

    return bool(_cached_probe(f"url:{target}", ttl_s, _load))


def _ain_phi_live() -> bool:
    def _load() -> bool:
        try:
            with urllib.request.urlopen(AIN_PHI_URL, timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if not isinstance(payload, dict):
                return False
            if bool(payload.get("ok", False)):
                return True
            return payload.get("phi") is not None and bool(str(payload.get("proxy_method") or "").strip())
        except Exception:
            return False

    return bool(_cached_probe("ain:phi", 5.0, _load))


def _discord_channel_message_count(channel_id: int, limit: int = 4000) -> int:
    rows = _read_jsonl(DISCORD_MESSAGES_PATH, limit=limit)
    count = 0
    for row in rows:
        try:
            row_channel = int(row.get("channel_id", 0) or 0)
        except Exception:
            continue
        if row_channel == int(channel_id):
            count += 1
    return count


def _is_review_managed_task(task: dict[str, Any]) -> bool:
    task_id = str(task.get("id") or "").strip()
    return task_id.startswith("rev-") or bool(str(task.get("review_requested_by") or "").strip())


def _review_task_is_working(task: dict[str, Any]) -> tuple[bool, str]:
    task_id = str(task.get("id") or "").strip()
    commit = str(task.get("commit") or "").strip()
    if commit and not _git_commit_exists(commit):
        return False, f"commit {commit} is not present in the repo"

    app_text = _read_text(APP_PY_PATH)
    static_js_text = _read_text(STATIC_APP_JS_PATH)
    static_index_text = _read_text(STATIC_INDEX_PATH)
    discord_bot_text = _read_text(DISCORD_BOT_SCRIPT_PATH)
    harness_text = _read_text(MODEL_PROMPT_HARNESSES_PATH)
    phi_metrics_text = _read_text(PHI_METRICS_PATH)

    if task_id == "rev-001":
        ok = (
            "_source_phi_data" in app_text
            and "fetch('/api/source/phi')" in static_js_text
            and _ain_phi_live()
        )
        return ok, "AIN phi endpoint and dashboard wiring are live" if ok else "AIN phi endpoint or dashboard wiring is missing"

    if task_id == "rev-002":
        ok = (
            "_source_coordination_feed" in app_text
            and "source/coordination-feed" in app_text
            and "#open-communication" in static_index_text
            and _discord_channel_message_count(ORCHESTRATOR_CHANNEL_ID) > 0
        )
        return ok, "open-communication feed has source data and UI wiring" if ok else "open-communication feed lacks data or UI wiring"

    if task_id == "rev-003":
        ok = (
            "_source_relational_data" in app_text
            and "fetch('/api/source/relational')" in static_js_text
            and bool(_read_jsonl(PAUSE_CHECK_LOG_PATH, limit=10))
            and "author_silhouette" in phi_metrics_text
        )
        return ok, "relational signals and dashboard wiring are live" if ok else "relational signals or dashboard wiring are incomplete"

    if task_id == "rev-004":
        ok = (
            _service_is_active("openclaw-discord-bot.service")
            and '"discord-orchestrator": "Dali 🎨"' in discord_bot_text
            and '"discord-clawd": "c_lawd 🜃"' in discord_bot_text
            and '"discord-clawd": "clawd_philosophical_interlocutor"' in harness_text
        )
        return ok, "multi-agent Discord bot process and lane config are live" if ok else "multi-agent Discord bot runtime or lane config is incomplete"

    return False, "no explicit working-state evidence rule is mapped for this review task"


def _reviewer_for_task(task: dict[str, Any]) -> str:
    existing = str(task.get("reviewer") or "").strip()
    if existing:
        return existing
    assignee = str(task.get("assignee") or "").strip()
    mapped = REVIEWER_BY_ASSIGNEE.get(assignee.lower())
    if mapped:
        return mapped
    return assignee or "c_lawd"


def _task_sort_key(task: dict[str, Any]) -> tuple[int, str, str]:
    return (
        PRIORITY_ORDER.get(str(task.get("priority") or "").strip().lower(), 99),
        str(task.get("created_at") or ""),
        str(task.get("id") or ""),
    )


def _task_requires_review_gate(task: dict[str, Any]) -> bool:
    if bool(task.get("read_only")):
        return False
    if str(task.get("origin") or "").strip() == "source_mission_config":
        return False
    return not _is_review_managed_task(task)


def _task_artifact_exists(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.exists()
    for root in (REPO_ROOT, SOURCE_UI_ROOT):
        if (root / raw).exists():
            return True
    return False


def _url_available(url: str, *, ttl_s: float = 5.0) -> bool:
    target = str(url or "").strip()
    if not target:
        return False

    def _load() -> bool:
        try:
            with urllib.request.urlopen(target, timeout=2.0) as response:
                status = int(getattr(response, "status", 200) or 200)
                return 200 <= status < 400
        except Exception:
            return False

    return bool(_cached_probe(f"url-available:{target}", ttl_s, _load))


def _task_work_is_complete(task: dict[str, Any]) -> tuple[bool, str]:
    commit = str(task.get("commit") or "").strip()
    artifact_path = str(task.get("artifact_path") or "").strip()
    verification_url = str(task.get("verification_url") or "").strip()

    checks: list[tuple[bool, str]] = []
    if commit:
        checks.append((_git_commit_exists(commit), f"commit {commit} is present in the repo"))
    if artifact_path:
        checks.append((_task_artifact_exists(artifact_path), f"artifact {artifact_path} exists"))
    if verification_url:
        checks.append((_url_available(verification_url), f"verification URL {verification_url} is reachable"))

    if not checks:
        return False, "no explicit work-completion evidence is attached to this task"

    failures = [reason for ok, reason in checks if not ok]
    if failures:
        return False, "; ".join(failures)
    return True, "; ".join(reason for _, reason in checks)


def _sanitize_task(task: dict[str, Any]) -> dict[str, Any]:
    row = dict(task)
    row["status"] = _normalize_task_status(row.get("status"))
    row["priority"] = _normalize_task_priority(row.get("priority"))
    review_gated = _task_requires_review_gate(row)

    progress = _coerce_progress(row.get("progress"))
    if progress is None:
        row.pop("progress", None)
    else:
        row["progress"] = progress

    if row["status"] == "done":
        row["progress"] = 100
        if review_gated and not str(row.get("reviewed_by") or "").strip():
            row["status"] = "review"
            row.pop("completed_at", None)
        else:
            row.setdefault("completed_at", _now_iso())
    elif progress is not None and progress >= 100:
        row["progress"] = 100
        if review_gated:
            row["status"] = "review"
            row.pop("completed_at", None)
        else:
            row["status"] = "done"
            row.setdefault("completed_at", _now_iso())

    if row["status"] == "review":
        row["reviewer"] = _reviewer_for_task(row)
        row.setdefault("review_requested_at", str(row.get("updated_at") or _now_iso()))
    else:
        row.pop("review_requested_at", None)
        if row["status"] != "done":
            row.pop("reviewed_by", None)
            row.pop("reviewed_at", None)

    return row


def _source_mission_task_id(sequence: int) -> str:
    return f"sm-{int(sequence):03d}"


def _source_mission_assignee(item: dict[str, Any], existing: dict[str, Any]) -> str:
    for key in ("assignee", "owner", "being", "lane"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    source_id = str(item.get("id") or "").strip().lower()
    mapped_assignee = SOURCE_MISSION_ASSIGNEE_BY_ID.get(source_id)
    if mapped_assignee:
        return mapped_assignee
    pillar = str(item.get("pillar") or "").strip().lower()
    mapped_assignee = SOURCE_MISSION_ASSIGNEE_BY_PILLAR.get(pillar)
    if mapped_assignee:
        return mapped_assignee
    existing_assignee = str(existing.get("assignee") or "").strip()
    return existing_assignee or "dali"


def _limited_glob_count(root: Path, pattern: str, limit: int = 24) -> int:
    if not root.exists():
        return 0
    try:
        return sum(1 for _, _ in zip(range(limit), root.rglob(pattern)))
    except Exception:
        return 0


def _match_normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").strip().lower()))


def _session_recent_texts(session_log: Path, *, limit: int = 12) -> list[str]:
    if not session_log.exists() or not session_log.is_file():
        return []
    texts: list[str] = []
    try:
        lines = session_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-120:]
    except Exception:
        return []
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
        role = str(message.get("role") or "").strip().lower()
        if role not in {"user", "assistant", "toolresult"}:
            continue
        text = _strip_transport_metadata(_extract_message_text(message))
        if not text or text.startswith("[cron:") or "HEARTBEAT_OK" in text:
            continue
        texts.append(_trim(text, limit=240))
    return texts[-max(1, int(limit)) :]


def _source_mission_runtime_claim_signals(
    *,
    agents_root: Path = AGENTS_ROOT,
    lookback_minutes: int = SOURCE_MISSION_CLAIM_LOOKBACK_MINUTES,
) -> dict[str, str]:
    now = _now_utc()
    cutoff = now.timestamp() - (max(1, int(lookback_minutes)) * 60)
    signals: dict[str, list[str]] = {}

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

        for session_id, (_, record) in deduped.items():
            updated_at = _parse_epoch_ms(record.get("updatedAt"))
            if updated_at is None:
                continue
            activity_state = ""
            if isinstance(record.get("acp"), dict):
                activity_state = str(record["acp"].get("state", "")).strip().lower()
            if _runtime_status(updated_at, activity_state) != "in_progress":
                continue
            session_log = sessions_path.parent / f"{session_id}.jsonl"
            title_hint, detail_hint = _session_tail_hint(session_log)
            candidate_texts = [title_hint or "", detail_hint or "", *_session_recent_texts(session_log)]
            normalized_parts = [_match_normalized_text(text) for text in candidate_texts if text]
            if not normalized_parts:
                continue
            signals.setdefault(agent_id, []).extend(part for part in normalized_parts if part)

    return {
        agent_id: " ".join(parts)
        for agent_id, parts in signals.items()
        if parts
    }


def _source_mission_claim_terms(task_id: str, source_id: str, title: str) -> list[str]:
    raw_terms = [task_id, source_id, title]
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", str(title or "").strip().lower())
        if len(token) >= 4 and token not in MISSION_CLAIM_TERM_STOPWORDS
    ]
    raw_terms.extend(" ".join(tokens[index : index + 2]) for index in range(len(tokens) - 1))

    seen: set[str] = set()
    terms: list[str] = []
    for raw in raw_terms:
        normalized = _match_normalized_text(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    return terms


def _source_mission_runtime_claim(
    *,
    assignee: str,
    task_id: str,
    source_id: str,
    title: str,
    runtime_claims: dict[str, str],
) -> tuple[bool, str]:
    aliases = set(SOURCE_MISSION_RUNTIME_ALIASES.get(str(assignee or "").strip(), set()))
    if not aliases:
        aliases = {str(assignee or "").strip()}
    terms = _source_mission_claim_terms(task_id, source_id, title)
    if not terms:
        return False, ""

    for alias in aliases:
        haystack = runtime_claims.get(alias, "")
        if not haystack:
            continue
        for term in terms:
            if term and term in haystack:
                return True, f"Active runtime or ingest activity from {alias} references {source_id} / {title}."
    return False, ""


def _source_mission_ingest_state(path: Path = BACKLOG_INGEST_STATE_PATH) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {}
    now_ts = time.time()
    state_by_task: dict[str, dict[str, Any]] = {}
    for raw in payload.values():
        if not isinstance(raw, dict):
            continue
        task_id = str(raw.get("task_id") or "").strip()
        if not task_id:
            continue
        outcome_kind = str(raw.get("outcome_kind") or "").strip()
        cooldown_until = float(raw.get("cooldown_until") or 0.0)
        if outcome_kind and cooldown_until and now_ts >= cooldown_until:
            continue
        current = state_by_task.get(task_id)
        candidate_ts = float(raw.get("outcome_seen_ts") or raw.get("staged_at") or 0.0)
        existing_ts = float((current or {}).get("outcome_seen_ts") or (current or {}).get("staged_at") or 0.0)
        if current is None or candidate_ts >= existing_ts:
            state_by_task[task_id] = dict(raw)
    return state_by_task


def _source_mission_outcome_override(
    *,
    task_id: str,
    status: str,
    reason: str,
    now_dt: datetime,
    ingest_state: dict[str, dict[str, Any]],
) -> tuple[str, str, dict[str, str]]:
    entry = ingest_state.get(task_id)
    if not isinstance(entry, dict):
        return status, reason, {}

    runtime_agent = str(entry.get("runtime_agent") or "").strip()
    stage_kind = str(entry.get("stage_kind") or "").strip()
    outcome_kind = str(entry.get("outcome_kind") or "").strip()
    outcome_text = _trim(str(entry.get("outcome_text") or "").strip(), limit=220)
    outcome_dt = _parse_iso_timestamp(entry.get("outcome_at"))
    if outcome_dt is None:
        try:
            outcome_seen_ts = float(entry.get("outcome_seen_ts") or 0.0)
        except Exception:
            outcome_seen_ts = 0.0
        if outcome_seen_ts > 0:
            outcome_dt = datetime.fromtimestamp(outcome_seen_ts, tz=timezone.utc)

    outcome_meta = {
        "ingest_runtime_agent": runtime_agent,
        "ingest_stage_kind": stage_kind,
        "ingest_outcome_kind": outcome_kind,
        "ingest_outcome_text": outcome_text,
        "ingest_outcome_at": str(entry.get("outcome_at") or _iso(outcome_dt) or ""),
    }
    actor = runtime_agent or "backlog-ingest"

    if status == "done" and outcome_kind != "result":
        return "done", reason, outcome_meta

    if outcome_kind == "blocker":
        detail = outcome_text or "no blocker detail was recorded"
        return "backlog", f"Backlog ingest blocker from {actor}: {detail}", outcome_meta

    if outcome_kind == "result":
        detail = outcome_text or "concrete progress was recorded"
        if status == "done":
            return "done", f"{reason} Result artifact recorded by {actor}: {detail}", outcome_meta
        age_seconds = 0.0
        if outcome_dt is not None:
            age_seconds = max(0.0, (now_dt - outcome_dt).total_seconds())
        if age_seconds < AUTO_REVIEW_SETTLE_SECONDS:
            return (
                "review",
                f"Result artifact recorded by {actor}: {detail} Awaiting definition-of-done verification.",
                outcome_meta,
            )
        return (
            "backlog",
            f"Result artifact recorded by {actor}, but definition-of-done evidence is still missing: {detail}",
            outcome_meta,
        )

    try:
        staged_at = float(entry.get("staged_at") or 0.0)
    except Exception:
        staged_at = 0.0
    if staged_at > 0.0:
        age_seconds = max(0.0, now_dt.timestamp() - staged_at)
        if age_seconds < SOURCE_MISSION_INGEST_LEASE_SECONDS and status != "done":
            if stage_kind == "repo_acp":
                detail = f"Backlog ingest staged to repo-capable {actor}; awaiting recorded result artifact."
            else:
                detail = f"Backlog ingest staged to {actor}; awaiting BACKLOG_RESULT or BACKLOG_BLOCKER artifact."
            return "in_progress", detail, outcome_meta
        if age_seconds >= SOURCE_MISSION_INGEST_LEASE_SECONDS:
            return (
                "backlog",
                f"Backlog ingest lease expired for {actor}: no BACKLOG_RESULT or BACKLOG_BLOCKER artifact was recorded.",
                outcome_meta,
            )

    return status, reason, outcome_meta


def _source_mission_signals() -> dict[str, Any]:
    task_store_text = _read_text(Path(__file__))
    portfolio_text = _read_text(PORTFOLIO_API_PATH)
    app_text = _read_text(APP_PY_PATH)
    static_js_text = _read_text(STATIC_APP_JS_PATH)
    components_text = _read_text(STATIC_COMPONENTS_JS_PATH)
    static_index_text = _read_text(STATIC_INDEX_PATH)
    static_css_text = _read_text(STATIC_CSS_PATH)
    discord_bot_text = _read_text(DISCORD_BOT_SUPPORT_PATH)
    discord_bridge_text = _read_text(DISCORD_BRIDGE_API_PATH)
    boundary_text = _read_text(BOUNDARY_STATE_API_PATH)
    discord_bot_script_text = _read_text(DISCORD_BOT_SCRIPT_PATH)
    harness_text = _read_text(MODEL_PROMPT_HARNESSES_PATH)
    user_inference_text = _read_text(USER_INFERENCE_API_PATH)
    agent_integration_text = _read_text(AGENT_INTEGRATION_DOC_PATH)
    phi_metrics_text = _read_text(PHI_METRICS_PATH)

    command_history = _read_json(COMMAND_HISTORY_PATH)
    command_receipts = _read_json(COMMAND_RECEIPTS_PATH)
    active_inferences = [
        row
        for row in _read_jsonl(USER_INFERENCES_PATH, limit=400)
        if str(row.get("status") or "active").strip().lower() == "active"
    ]
    preference_profile = _read_json(PREFERENCE_PROFILE_PATH)
    research_rows = _read_jsonl(DISCORD_RESEARCH_PATH, limit=200)
    pause_rows = _read_jsonl(PAUSE_CHECK_LOG_PATH, limit=20)

    profile_sections = []
    if isinstance(preference_profile, dict):
        profile_sections = [
            key
            for key in preference_profile.keys()
            if key not in {"schema_version", "subject", "updated_at"}
        ]

    return {
        "command_history_count": len(command_history) if isinstance(command_history, list) else 0,
        "command_receipt_count": len(command_receipts) if isinstance(command_receipts, list) else 0,
        "has_portfolio_packet": 'payload["source_mission"]' in portfolio_text and 'payload["operator_timeline"]' in portfolio_text,
        "has_portfolio_ui": "const sourceMission = portfolio.source_mission" in static_js_text
        and "const operatorTimeline = portfolio.operator_timeline" in static_js_text,
        "has_context_packet_api": "def build_source_context_packet" in portfolio_text
        and '"context_packet"' in portfolio_text
        and '"recency_markers"' in portfolio_text
        and '"open_work"' in portfolio_text
        and '"active_models"' in portfolio_text
        and '"preference_lines"' in portfolio_text,
        "has_context_packet_ui": "mission.context_packet" in static_js_text
        and "source-mission-summary" in static_index_text,
        "has_context_packet_discord": "source_context_packet_text" in discord_bot_text
        and "Current Source context:" in discord_bot_text,
        "has_discord_bridge": "portfolio_payload" in discord_bot_text and "discord_bridge" in static_js_text,
        "has_local_context_packet": "build_user_context_packet" in discord_bot_text
        and "sync_preference_packet_to_workspaces" in user_inference_text,
        "has_queryable_preference_graph": "def query_preference_graph" in user_inference_text
        and '"matched_sections"' in user_inference_text
        and '"prompt_lines"' in user_inference_text,
        "has_contextual_preference_harness": "def user_context_packet_text(" in discord_bot_text
        and "query_preference_graph(" in discord_bot_text
        and "user_context_packet_text(" in discord_bot_script_text
        and "context=f\"{getattr(message.channel, 'name', '') or ''}" in discord_bot_script_text,
        "has_operator_timeline_ui": "_build_operator_timeline" in portfolio_text
        and "operator-timeline-list" in static_index_text
        and "function renderOperatorTimeline" in static_js_text,
        "inference_count": len(active_inferences),
        "has_inference_evidence": any(bool(row.get("evidence_refs")) for row in active_inferences),
        "has_inference_confidence": any(row.get("confidence") is not None for row in active_inferences),
        "has_inference_review_state": any(str(row.get("review_state") or "").strip() for row in active_inferences),
        "all_inferences_have_evidence": bool(active_inferences) and all(bool(row.get("evidence_refs")) for row in active_inferences),
        "all_inferences_have_confidence": bool(active_inferences) and all(row.get("confidence") is not None for row in active_inferences),
        "all_inferences_have_review_state": bool(active_inferences) and all(str(row.get("review_state") or "").strip() for row in active_inferences),
        "all_inferences_have_contradiction_state": bool(active_inferences) and all(str(row.get("contradiction_state") or "").strip() for row in active_inferences),
        "all_inferences_have_operator_actions": bool(active_inferences) and all(bool(row.get("operator_actions")) for row in active_inferences),
        "has_inference_review_api": "update_user_inference" in user_inference_text
        and "/api/user-inferences/" in app_text,
        "has_inference_review_ui": "data-inference-review" in static_js_text
        and "api.updateUserInference" in static_js_text,
        "profile_section_count": len(profile_sections),
        "research_count": len(research_rows),
        "has_research_promotion_api": "def promote_research_item" in task_store_text
        and "/api/research/promote" in app_text,
        "has_research_promotion_ui": "openResearchPromotionModal" in static_js_text
        and "api.promoteResearchItem" in static_js_text,
        "has_research_source_links": "source_links" in task_store_text
        and "task-source-link" in components_text,
        "teamchat_count": _limited_glob_count(TEAMCHAT_ROOT, "*.json"),
        "has_relational_endpoint": "source/relational" in app_text,
        "has_relational_ui": "ci-relational-card" in static_index_text
        and "fetch('/api/source/relational')" in static_js_text,
        "has_relational_harness_adaptation": "build_relational_prompt_lines" in discord_bot_text
        and "relational_heading" in discord_bot_text
        and '"relational_modes"' in harness_text,
        "pause_check_count": len(pause_rows),
        "has_diversity_metric": "author_silhouette" in phi_metrics_text,
        "has_approval_flow": "pending_approval" in app_text and "approvalButton" in static_js_text,
        "has_boundary_payload": "def build_memory_source_boundary" in boundary_text
        and '"boundary"' in portfolio_text
        and "build_discord_channel_boundary" in discord_bridge_text
        and "build_command_receipt_boundary" in app_text,
        "has_boundary_ui": "function renderBoundaryState" in static_js_text
        and "boundary-state" in static_css_text
        and "memory-sources-list" in static_index_text,
        "has_runtime_mirror": bool(_runtime_source_entries()) or "GET /api/runtime-tasks" in agent_integration_text,
        "has_task_create_flow": "task_create_text" in discord_bot_text and "create_task(" in discord_bot_text,
        "has_task_state": TASKS_PATH.exists(),
        "runtime_claims": _source_mission_runtime_claim_signals(),
    }


def _source_mission_status(source_id: str, signals: dict[str, Any]) -> tuple[str, str]:
    if source_id == "source-001":
        if (
            signals["has_context_packet_api"]
            and signals["has_context_packet_ui"]
            and signals["has_context_packet_discord"]
            and signals["has_local_context_packet"]
            and signals["profile_section_count"] > 0
        ):
            return "done", "Canonical context packet now carries recency markers, open work, active models, and human preference lines into Source UI and Discord."
        if signals["has_context_packet_api"] and signals["has_context_packet_ui"]:
            return "review", "Canonical context packet exists and is rendered in Source UI, but downstream consumption is still partial."
        return "backlog", "No shared cross-surface context packet evidence found yet."
    if source_id == "source-002":
        if signals["has_operator_timeline_ui"] and signals["command_history_count"] > 0:
            return "done", "Operator timeline is built and rendered against live command history."
        if signals["has_operator_timeline_ui"]:
            return "review", "Timeline view is wired, but live event history is sparse."
        return "backlog", "No unified operator timeline is exposed yet."
    if source_id == "source-003":
        if (
            signals["all_inferences_have_evidence"]
            and signals["all_inferences_have_confidence"]
            and signals["all_inferences_have_review_state"]
            and signals["all_inferences_have_contradiction_state"]
            and signals["all_inferences_have_operator_actions"]
            and signals["has_inference_review_api"]
            and signals["has_inference_review_ui"]
        ):
            return "done", "Durable inferences now surface evidence links, contradiction state, confidence, and operator review actions."
        if (
            signals["all_inferences_have_evidence"]
            and signals["all_inferences_have_confidence"]
            and signals["all_inferences_have_review_state"]
            and signals["all_inferences_have_contradiction_state"]
        ):
            return "review", "Inference rows carry the full evidence metadata, but the operator review action surface is not complete yet."
        if signals["inference_count"] > 0:
            return "backlog", "Inference rows are being distilled, but review metadata is incomplete."
        return "backlog", "No active durable inference rows found."
    if source_id == "source-004":
        if signals["has_queryable_preference_graph"] and signals["has_contextual_preference_harness"]:
            return "done", "Prompt harnesses now request targeted preference packets by context from the distilled inference graph."
        if signals["has_queryable_preference_graph"] and signals["has_local_context_packet"]:
            return "review", "The preference graph is queryable, but prompt harnesses are not all using contextual packets yet."
        if signals["profile_section_count"] > 0 and signals["has_local_context_packet"]:
            return "backlog", "Structured preference sections and workspace context packets exist, but the model is still a profile, not a queryable graph."
        if signals["profile_section_count"] > 0:
            return "backlog", "Preference structure exists, but packet sync is incomplete."
        return "backlog", "No structured inference profile found."
    if source_id == "source-005":
        if (
            signals["has_relational_endpoint"]
            and signals["has_relational_ui"]
            and signals["has_relational_harness_adaptation"]
            and (signals["pause_check_count"] > 0 or signals["has_diversity_metric"])
        ):
            return "done", "Relational state is live in Source UI and the Discord prompt harnesses now adapt response style from it."
        if (
            signals["has_relational_endpoint"]
            and signals["has_relational_ui"]
            and (signals["pause_check_count"] > 0 or signals["has_diversity_metric"])
        ):
            return "review", "Live relational signals are exposed in the UI, but harness-side adaptation is still partial."
        if signals["has_relational_endpoint"] and signals["has_relational_ui"]:
            return "backlog", "Relational card wiring exists, but live relational signals are still thin."
        return "backlog", "No live relational-state surface detected."
    if source_id == "source-006":
        return "backlog", "TeamChat and runtime lanes exist, but there is no explicit deliberation-cell contract with roles, synthesis, and dissent yet."
    if source_id == "source-007":
        if (
            signals["has_research_promotion_api"]
            and signals["has_research_promotion_ui"]
            and signals["has_research_source_links"]
        ):
            return "done", "Research rows can now be promoted into owned tasks or experiments with attached source links in one flow."
        if signals["research_count"] > 0 and signals["has_task_create_flow"]:
            return "backlog", "Research ingest and task creation exist, but one-step research-to-task distillation with source links is not complete."
        if signals["research_count"] > 0:
            return "backlog", "Research messages are being ingested, but they are not yet promoted directly into owned action."
        return "backlog", "No research-to-action distillation evidence found."
    if source_id == "source-008":
        if signals["has_approval_flow"] and signals["has_local_context_packet"] and signals["has_boundary_payload"] and signals["has_boundary_ui"]:
            return "done", "Memory sources, prompt packets, outbound bridge previews, and approval receipts now show provenance/shareability boundary state before use."
        if signals["has_boundary_payload"] or signals["has_boundary_ui"]:
            return "review", "Boundary metadata is partially wired, but not every live surface is rendering it yet."
        if signals["has_approval_flow"]:
            return "backlog", "Approval controls exist, but cross-surface provenance is incomplete."
        return "backlog", "No consent/provenance boundary flow detected."
    if source_id == "source-009":
        return "backlog", "No weekly evolution report artifact or scheduler-backed review loop is wired yet."
    if source_id == "source-010":
        if (
            signals["has_portfolio_packet"]
            and signals["has_runtime_mirror"]
            and signals["has_task_state"]
            and signals["command_history_count"] > 0
            and signals["inference_count"] > 0
        ):
            return "done", "Portfolio payload already reconstructs active work, recent decisions, memory state, and runtime context for restart."
        if signals["has_portfolio_packet"] and signals["has_task_state"]:
            return "review", "Core restart state is bundled, but continuity coverage is still partial."
        return "backlog", "No restart packet coverage detected."
    return "backlog", "No mission evidence mapping defined."


def _source_mission_task_row(
    item: dict[str, Any],
    *,
    sequence: int,
    existing: dict[str, Any],
    signals: dict[str, Any],
    ingest_state: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    task_id = _source_mission_task_id(sequence)
    source_id = str(item.get("id") or task_id).strip() or task_id
    status, reason = _source_mission_status(source_id, signals)
    now_dt = _now_utc()
    now = _iso(now_dt) or _now_iso()
    existing_status = _normalize_task_status(existing.get("status"))
    assignee = _source_mission_assignee(item, existing)
    title = str(item.get("title") or f"Source Mission {sequence}").strip()
    if status == "backlog":
        claimed, claim_reason = _source_mission_runtime_claim(
            assignee=assignee,
            task_id=task_id,
            source_id=source_id,
            title=title,
            runtime_claims=dict(signals.get("runtime_claims") or {}),
        )
        if claimed:
            status = "in_progress"
            reason = claim_reason
    status, reason, outcome_meta = _source_mission_outcome_override(
        task_id=task_id,
        status=status,
        reason=reason,
        now_dt=now_dt,
        ingest_state=ingest_state,
    )
    if status == "done" and existing_status != "done":
        requested_at = _parse_iso_timestamp(existing.get("review_requested_at")) or now_dt
        if existing_status != "review" or (now_dt - requested_at).total_seconds() < AUTO_REVIEW_SETTLE_SECONDS:
            status = "review"
            reason = f"{reason} Awaiting automatic review completion."
    row = dict(existing)
    row.update(
        {
            "id": task_id,
            "title": title,
            "description": str(item.get("summary") or item.get("description") or "").strip(),
            "status": status,
            "priority": str(item.get("priority") or existing.get("priority") or "medium").strip() or "medium",
            "assignee": assignee,
            "project": "source-mission",
            "origin": "source_mission_config",
            "segment": str(item.get("pillar") or existing.get("segment") or "").strip(),
            "mission_task_id": source_id,
            "sequence": sequence,
            "definition_of_done": str(item.get("definition_of_done") or "").strip(),
            "status_reason": reason,
            "progress": SOURCE_MISSION_PROGRESS[status],
        }
    )
    for key in ("ingest_runtime_agent", "ingest_stage_kind", "ingest_outcome_kind", "ingest_outcome_text", "ingest_outcome_at"):
        value = str(outcome_meta.get(key) or "").strip()
        if value:
            row[key] = value
        else:
            row.pop(key, None)
    if status != "done":
        row["fix_instructions"] = f"Fix required: {reason} Definition of done: {str(item.get('definition_of_done') or '').strip()}"
    else:
        row.pop("fix_instructions", None)
    created_at = str(existing.get("created_at") or now)
    row["created_at"] = created_at

    if status in {"in_progress", "review", "done"}:
        row["started_at"] = str(existing.get("started_at") or now)
    else:
        row.pop("started_at", None)

    if status == "review":
        row["reviewer"] = _reviewer_for_task(row)
        row["review_requested_at"] = str(existing.get("review_requested_at") or now)
        row.pop("reviewed_by", None)
        row.pop("reviewed_at", None)
    elif status == "done":
        row["reviewer"] = str(existing.get("reviewer") or _reviewer_for_task(row))
        row["reviewed_by"] = str(existing.get("reviewed_by") or row["reviewer"])
        row["reviewed_at"] = str(existing.get("reviewed_at") or now)
        row.pop("review_requested_at", None)
    else:
        row.pop("review_requested_at", None)
        row.pop("reviewed_by", None)
        row.pop("reviewed_at", None)

    if status == "done":
        row["completed_at"] = str(existing.get("completed_at") or now)
    else:
        row.pop("completed_at", None)

    if row != existing:
        row["updated_at"] = now
    elif existing.get("updated_at"):
        row["updated_at"] = str(existing["updated_at"])

    return row


def _merge_source_mission_tasks(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    payload = _read_json(SOURCE_MISSION_CONFIG_PATH)
    raw_tasks = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(raw_tasks, list):
        return tasks, False

    existing_by_id = {
        str(task.get("id") or ""): task
        for task in tasks
        if isinstance(task, dict)
    }
    signals = _source_mission_signals()
    ingest_state = _source_mission_ingest_state()
    mission_rows: list[dict[str, Any]] = []
    valid_ids: set[str] = set()
    changed = False

    for sequence, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            continue
        task_id = _source_mission_task_id(sequence)
        valid_ids.add(task_id)
        existing = existing_by_id.get(task_id, {})
        row = _source_mission_task_row(
            item,
            sequence=sequence,
            existing=existing,
            signals=signals,
            ingest_state=ingest_state,
        )
        if row != existing:
            changed = True
        mission_rows.append(row)

    next_tasks: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            changed = True
            continue
        task_id = str(task.get("id") or "")
        if str(task.get("origin") or "") == "source_mission_config":
            if task_id not in valid_ids:
                changed = True
            continue
        next_tasks.append(task)

    next_tasks.extend(mission_rows)
    return next_tasks, changed


def _reconcile_review_tasks(tasks: list[dict[str, Any]]) -> bool:
    changed = False
    for task in tasks:
        if not _is_review_managed_task(task):
            continue

        reviewer = _reviewer_for_task(task)
        task["reviewer"] = reviewer
        working, reason = _review_task_is_working(task)
        review_status_reason = str(task.get("review_status_reason") or "")
        if review_status_reason != reason:
            task["review_status_reason"] = reason
            changed = True

        current_status = _normalize_task_status(task.get("status"))
        if working:
            if current_status != "done":
                reviewed_at = _now_iso()
                task["status"] = "done"
                task["progress"] = 100
                task["reviewed_by"] = reviewer
                task["reviewed_at"] = reviewed_at
                task["completed_at"] = reviewed_at
                task["updated_at"] = reviewed_at
                task.pop("review_requested_at", None)
                task.pop("fix_instructions", None)
                changed = True
            else:
                task.setdefault("progress", 100)
                task.setdefault("reviewed_by", reviewer)
                task.setdefault("reviewed_at", str(task.get("completed_at") or _now_iso()))
                task.pop("fix_instructions", None)
        else:
            next_status = "backlog"
            next_progress = SOURCE_MISSION_PROGRESS["backlog"]
            if current_status != next_status:
                task["status"] = next_status
                task["progress"] = next_progress
                task["updated_at"] = _now_iso()
                changed = True
            task["fix_instructions"] = f"Fix required before review passes: {reason}"
            task.pop("completed_at", None)
            task.pop("reviewed_by", None)
            task.pop("reviewed_at", None)
            task.pop("review_requested_at", None)

    return changed


def _reconcile_auto_review_gate_tasks(tasks: list[dict[str, Any]]) -> bool:
    changed = False
    now_dt = _now_utc()
    now_iso = _iso(now_dt) or _now_iso()

    for task in tasks:
        if not _task_requires_review_gate(task):
            continue

        current_status = _normalize_task_status(task.get("status"))
        if current_status not in {"in_progress", "review", "done"}:
            continue

        complete, reason = _task_work_is_complete(task)
        if str(task.get("work_status_reason") or "") != reason:
            task["work_status_reason"] = reason
            changed = True

        if current_status == "in_progress":
            if not complete:
                continue
            task["status"] = "review"
            task["progress"] = 100
            task["reviewer"] = _reviewer_for_task(task)
            task["review_requested_at"] = str(task.get("review_requested_at") or now_iso)
            task["updated_at"] = now_iso
            task.pop("completed_at", None)
            task.pop("fix_instructions", None)
            changed = True
            continue

        if current_status == "review":
            if not complete:
                task["status"] = "in_progress"
                task["progress"] = min(int(task.get("progress") or 55), 95)
                task["updated_at"] = now_iso
                task["fix_instructions"] = f"Fix required before review passes: {reason}"
                task.pop("completed_at", None)
                task.pop("reviewed_by", None)
                task.pop("reviewed_at", None)
                task.pop("review_requested_at", None)
                changed = True
                continue

            requested_at = _parse_iso_timestamp(task.get("review_requested_at")) or now_dt
            if (now_dt - requested_at).total_seconds() < AUTO_REVIEW_SETTLE_SECONDS:
                continue

            task["status"] = "done"
            task["progress"] = 100
            task["reviewer"] = _reviewer_for_task(task)
            task["reviewed_by"] = str(task.get("reviewed_by") or task["reviewer"])
            task["reviewed_at"] = str(task.get("reviewed_at") or now_iso)
            task["completed_at"] = str(task.get("completed_at") or task["reviewed_at"])
            task["updated_at"] = now_iso
            task.pop("fix_instructions", None)
            changed = True
            continue

        if current_status == "done" and not complete:
            task["status"] = "in_progress"
            task["progress"] = 55
            task["updated_at"] = now_iso
            task["fix_instructions"] = f"Fix required before review passes: {reason}"
            task.pop("completed_at", None)
            task.pop("reviewed_by", None)
            task.pop("reviewed_at", None)
            changed = True

    return changed


def _reconcile_local_tasks(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    normalized: list[dict[str, Any]] = []
    changed = False

    for task in tasks:
        if not isinstance(task, dict):
            continue
        row = _sanitize_task(task)
        if row != task:
            changed = True
        normalized.append(row)

    if _reconcile_review_tasks(normalized):
        changed = True

    if _reconcile_auto_review_gate_tasks(normalized):
        changed = True

    active_assignees = {
        str(task.get("assignee") or "").strip().lower()
        for task in normalized
        if task.get("status") == "in_progress" and str(task.get("assignee") or "").strip()
    }

    backlog_by_assignee: dict[str, list[dict[str, Any]]] = {}
    for task in normalized:
        assignee = str(task.get("assignee") or "").strip().lower()
        if task.get("status") != "backlog" or not assignee:
            continue
        if str(task.get("origin") or "").strip() == "source_mission_config":
            continue
        backlog_by_assignee.setdefault(assignee, []).append(task)

    for assignee, backlog in backlog_by_assignee.items():
        if assignee in active_assignees:
            continue
        backlog.sort(key=_task_sort_key)
        next_task = backlog[0]
        if next_task.get("status") != "in_progress":
            next_task["status"] = "in_progress"
            next_task.setdefault("started_at", _now_iso())
            next_task.setdefault("progress", 0)
            next_task["updated_at"] = _now_iso()
            active_assignees.add(assignee)
            changed = True

    return normalized, changed


def load_tasks(path: Path = TASKS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        _write_json_atomic(path, DEFAULT_TASKS)
        tasks = [dict(task) for task in DEFAULT_TASKS]
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            tasks = [dict(task) for task in DEFAULT_TASKS]
        else:
            tasks = [task for task in payload if isinstance(task, dict)] if isinstance(payload, list) else [dict(task) for task in DEFAULT_TASKS]
    tasks, source_changed = _merge_source_mission_tasks(tasks)
    reconciled, changed = _reconcile_local_tasks(tasks)
    if changed or source_changed:
        save_tasks(reconciled, path)
    return reconciled


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
    timestamp = _now_iso()
    task = {
        "id": next_task_id(tasks),
        "title": str(data.get("title", "")).strip(),
        "description": str(data.get("description", "")).strip(),
        "status": str(data.get("status", "backlog")).strip() or "backlog",
        "priority": str(data.get("priority", "medium")).strip() or "medium",
        "assignee": str(data.get("assignee", "")).strip(),
        "project": str(data.get("project", "")).strip(),
        "origin": str(data.get("origin", "dashboard")).strip() or "dashboard",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    task_kind = str(data.get("task_kind") or "").strip()
    if task_kind or task.get("origin") == RESEARCH_PROMOTION_ORIGIN:
        task["task_kind"] = _normalize_task_kind(task_kind)

    source_refs = [
        str(ref).strip()
        for ref in (data.get("source_refs") or [])
        if str(ref).strip()
    ]
    if source_refs:
        task["source_refs"] = source_refs

    source_links = _normalize_source_links(data.get("source_links"))
    if source_links:
        task["source_links"] = source_links

    research_item_id = str(data.get("research_item_id") or "").strip()
    if research_item_id:
        task["research_item_id"] = research_item_id

    source_excerpt = str(data.get("source_excerpt") or "").strip()
    if source_excerpt:
        task["source_excerpt"] = source_excerpt

    reconciled, _ = _reconcile_local_tasks([*tasks, task])
    save_tasks(reconciled, path)
    return next((row for row in reconciled if str(row.get("id")) == str(task["id"])), task)


def update_task(task_id: str, updates: dict[str, Any], path: Path = TASKS_PATH) -> dict[str, Any] | None:
    tasks = load_tasks(path)
    for task in tasks:
        if str(task.get("id")) != str(task_id):
            continue
        previous_status = _normalize_task_status(task.get("status"))
        task.update({key: value for key, value in updates.items() if value is not None})
        next_status = _normalize_task_status(task.get("status"))
        if next_status == "review":
            task["review_requested_at"] = _now_iso()
            task["reviewer"] = _reviewer_for_task(task)
        elif next_status == "done":
            if previous_status == "review" or not _task_requires_review_gate(task):
                reviewed_at = _now_iso()
                task["reviewed_by"] = str(task.get("reviewed_by") or _reviewer_for_task(task))
                task["reviewed_at"] = reviewed_at
                task["completed_at"] = str(task.get("completed_at") or reviewed_at)
            else:
                task["status"] = "review"
                task["review_requested_at"] = _now_iso()
                task["reviewer"] = _reviewer_for_task(task)
                task.pop("completed_at", None)
        else:
            task.pop("review_requested_at", None)
        task["updated_at"] = _now_iso()
        reconciled, _ = _reconcile_local_tasks(tasks)
        save_tasks(reconciled, path)
        return next((row for row in reconciled if str(row.get("id")) == str(task_id)), task)
    return None


def delete_task(task_id: str, path: Path = TASKS_PATH) -> bool:
    tasks = load_tasks(path)
    next_tasks = [task for task in tasks if str(task.get("id")) != str(task_id)]
    if len(next_tasks) == len(tasks):
        return False
    save_tasks(next_tasks, path)
    return True


# ---------------------------------------------------------------------------
# Archive support
# ---------------------------------------------------------------------------

ARCHIVED_TASKS_PATH = SOURCE_UI_ROOT / "state" / "archived_tasks.json"


def load_archived_tasks(path: Path = ARCHIVED_TASKS_PATH) -> list[dict[str, Any]]:
    """Return all archived tasks (newest first)."""
    payload = _read_json(path)
    if not isinstance(payload, list):
        return []
    return [task for task in payload if isinstance(task, dict)]


def archive_task(task_id: str, path: Path = TASKS_PATH, archive_path: Path = ARCHIVED_TASKS_PATH) -> dict[str, Any] | None:
    """Move a task from tasks.json into archived_tasks.json.

    Returns the archived task dict or None if task_id not found.
    """
    tasks = load_tasks(path)
    target = next((t for t in tasks if str(t.get("id")) == str(task_id)), None)
    if target is None:
        return None

    remaining = [t for t in tasks if str(t.get("id")) != str(task_id)]
    save_tasks(remaining, path)

    archived = load_archived_tasks(archive_path)
    target = dict(target)
    target["archived_at"] = _now_iso()
    target["status"] = "archived"
    archived.insert(0, target)
    _write_json_atomic(archive_path, archived)
    return target
