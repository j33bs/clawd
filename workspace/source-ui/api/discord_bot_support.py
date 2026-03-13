"""Discord bot helpers backed by canonical local state."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .discord_memory import build_discord_memory_context
from .user_inference import build_user_context_packet
from .portfolio import portfolio_payload
from .task_store import create_task, load_tasks, update_task

ALLOWED_TASK_STATUSES = ("backlog", "in_progress", "review", "done")
ALLOWED_PRIORITIES = ("low", "medium", "high")
REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_HARNESS_CONFIG_PATH = REPO_ROOT / "workspace" / "source-ui" / "config" / "model_prompt_harnesses.json"


def _truncate(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def parse_channel_agent_map(raw: str) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for chunk in (raw or "").split(","):
        entry = chunk.strip()
        if not entry or "=" not in entry:
            continue
        channel_raw, agent_raw = entry.split("=", 1)
        channel_raw = channel_raw.strip()
        agent_id = agent_raw.strip()
        if channel_raw.isdigit() and agent_id:
            mapping[int(channel_raw)] = agent_id
    return mapping


@lru_cache(maxsize=1)
def load_prompt_harness_config() -> dict[str, Any]:
    if not PROMPT_HARNESS_CONFIG_PATH.exists():
        return {}
    try:
        payload = json.loads(PROMPT_HARNESS_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def prompt_harness_for_agent(agent_id: str | None) -> dict[str, Any]:
    config = load_prompt_harness_config()
    profiles = dict(config.get("profiles") or {})
    agent_map = dict(config.get("agent_map") or {})
    default_profile_name = str(config.get("default_profile") or "").strip()
    profile_name = str(agent_map.get(agent_id or "", default_profile_name) or "").strip()
    profile = profiles.get(profile_name)
    if isinstance(profile, dict):
        return {"name": profile_name, **profile}
    fallback = profiles.get(default_profile_name)
    if isinstance(fallback, dict):
        return {"name": default_profile_name, **fallback}
    return {
        "name": "default",
        "intro_lines": [
            "You are replying inside a Discord server chat channel.",
            "Respond conversationally and directly to the latest user message.",
            "Keep formatting Discord-safe and concise unless depth is requested.",
        ],
        "preference_heading": "Stable user preferences:",
        "memory_heading": "Relevant prior context:",
        "attachment_heading": "Attachments:",
    }


def build_discord_chat_prompt(
    *,
    agent_id: str | None = None,
    author_name: str,
    channel_name: str,
    content: str,
    attachments: list[str] | None = None,
    memory_context: list[str] | None = None,
    user_context: list[str] | None = None,
) -> str:
    harness = prompt_harness_for_agent(agent_id)
    intro_lines = [
        str(line).strip()
        for line in list(harness.get("intro_lines") or [])
        if str(line).strip()
    ]
    if not intro_lines:
        intro_lines = [
            "You are replying inside a Discord server chat channel.",
            "Respond conversationally and directly to the latest user message.",
        ]
    lines = [
        *intro_lines,
        f"Harness: {harness.get('name', 'default')}",
        f"Channel: #{channel_name or 'unknown'}",
        f"Author: {author_name or 'unknown'}",
        "",
        "Latest message:",
        content.strip() or "[no text content]",
    ]
    if user_context:
        lines.extend(["", str(harness.get("preference_heading") or "Stable user preferences:").strip(), *user_context[:6]])
    if memory_context:
        lines.extend(["", str(harness.get("memory_heading") or "Relevant prior context:").strip(), *memory_context[:6]])
    if attachments:
        lines.extend(["", str(harness.get("attachment_heading") or "Attachments:").strip()])
        lines.extend(f"- {item}" for item in attachments[:5])
    return "\n".join(lines)


def discord_memory_context_text(
    *,
    channel_id: int,
    author_name: str,
    exclude_message_id: int | None = None,
    limit: int = 4,
) -> list[str]:
    return build_discord_memory_context(
        channel_id=channel_id,
        author_name=author_name,
        exclude_message_id=exclude_message_id,
        limit=limit,
    )


def user_context_packet_text(limit: int = 4) -> list[str]:
    return build_user_context_packet(limit=limit)


def extract_agent_reply_text(payload: dict[str, Any]) -> str:
    responses = list(payload.get("payloads") or [])
    text_parts = [str(item.get("text") or "").strip() for item in responses]
    text = "\n\n".join(part for part in text_parts if part)
    if text:
        return _truncate(text, limit=1900)
    meta = dict(payload.get("meta") or {})
    return _truncate(str(meta.get("error") or "No response text returned."), limit=1900)


def extract_last_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    text = raw.strip()
    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if text[index + end :].strip():
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("No trailing JSON object found in command output.")


def _find_sim(portfolio: dict[str, Any], sim_id: str | None) -> list[dict[str, Any]]:
    sims = list(portfolio.get("sims") or [])
    if sim_id:
        normalized = sim_id.strip().lower()
        sims = [sim for sim in sims if str(sim.get("id", "")).lower() == normalized]
    return sims


def _find_project(portfolio: dict[str, Any], project_id: str | None) -> list[dict[str, Any]]:
    projects = list(portfolio.get("projects") or [])
    if project_id:
        normalized = project_id.strip().lower()
        projects = [project for project in projects if str(project.get("id", "")).lower() == normalized]
    return projects


def ops_health_text() -> str:
    payload = portfolio_payload()
    components = list(payload.get("components") or [])
    metrics = dict(payload.get("health_metrics") or {})
    work_items = list(payload.get("work_items") or [])
    lines = [
        "**Ops Health**",
        f"- CPU: {metrics.get('cpu', 0)}%",
        f"- Memory: {metrics.get('memory', 0)}%",
        f"- Disk: {metrics.get('disk', 0)}%",
        f"- GPU: {metrics.get('gpu', 0)}%",
    ]
    for component in components[:5]:
        lines.append(f"- {component.get('name', component.get('id', 'component'))}: {component.get('status', 'unknown')}")
    for item in work_items[:3]:
        lines.append(f"- Work: {item.get('title', item.get('id', 'work'))} :: {item.get('status', 'idle')}")
    return _truncate("\n".join(lines))


def sim_status_text(sim_id: str | None = None) -> str:
    payload = portfolio_payload()
    sims = _find_sim(payload, sim_id)
    if not sims:
        return f"No sims matched `{sim_id}`." if sim_id else "No sim data available."
    lines = ["**Sim Status**"]
    for sim in sims[:6]:
        lines.append(
            f"- {sim.get('id')}: {float(sim.get('net_return_pct', 0.0)):+.2f}% | "
            f"equity ${float(sim.get('final_equity', 0.0)):.2f} | "
            f"fees ${float(sim.get('fees_usd', 0.0)):.2f} | "
            f"{'halted' if sim.get('halted') else 'live'}"
        )
    return _truncate("\n".join(lines))


def project_status_text(project_id: str | None = None) -> str:
    payload = portfolio_payload()
    projects = _find_project(payload, project_id)
    if not projects:
        return f"No projects matched `{project_id}`." if project_id else "No projects configured."
    tasks = load_tasks()
    lines = ["**Project Status**"]
    for project in projects[:5]:
        pid = str(project.get("id", ""))
        scoped_tasks = [task for task in tasks if str(task.get("project", "")).strip() == pid]
        open_tasks = [task for task in scoped_tasks if str(task.get("status", "")).lower() != "done"]
        lines.append(
            f"- {project.get('name', pid)}: {project.get('status', 'idle')} | "
            f"{len(open_tasks)} open tasks | "
            f"{project.get('signals', 0)} signals"
        )
    return _truncate("\n".join(lines))


def task_create_text(
    title: str,
    description: str = "",
    priority: str = "medium",
    assignee: str = "",
    project: str = "",
) -> str:
    normalized_priority = priority.strip().lower() if priority else "medium"
    if normalized_priority not in ALLOWED_PRIORITIES:
        normalized_priority = "medium"
    task = create_task(
        {
            "title": title,
            "description": description,
            "priority": normalized_priority,
            "assignee": assignee,
            "project": project,
            "status": "backlog",
            "origin": "discord",
        }
    )
    scope = task.get("project") or "unscoped"
    owner = task.get("assignee") or "unassigned"
    return _truncate(
        "\n".join(
            [
                "**Task Created**",
                f"- id: #{task.get('id')}",
                f"- title: {task.get('title')}",
                f"- project: {scope}",
                f"- priority: {task.get('priority')}",
                f"- assignee: {owner}",
            ]
        )
    )


def task_move_text(task_id: int | str, status: str) -> str:
    normalized_status = status.strip().lower()
    if normalized_status not in ALLOWED_TASK_STATUSES:
        return f"Unsupported status `{status}`. Use one of: {', '.join(ALLOWED_TASK_STATUSES)}."
    task = update_task(str(task_id), {"status": normalized_status, "origin": "discord"})
    if task is None:
        return f"Task `{task_id}` not found."
    return _truncate(
        "\n".join(
            [
                "**Task Updated**",
                f"- id: #{task.get('id')}",
                f"- title: {task.get('title')}",
                f"- status: {task.get('status')}",
                f"- project: {task.get('project') or 'unscoped'}",
            ]
        )
    )
