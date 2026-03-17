"""Discord bot helpers backed by canonical local state."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from .discord_memory import build_discord_memory_context
except Exception:  # pragma: no cover
    def build_discord_memory_context(*, channel_id: int, author_name: str, exclude_message_id: int | None = None, limit: int = 4) -> list[str]:
        return []
from .telegram_memory import build_telegram_memory_context
from .relational_state import build_relational_prompt_lines
from .user_inference import build_user_context_packet, query_preference_graph
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


def _signed_currency(value: Any) -> str:
    amount = float(value or 0.0)
    return f"{'+' if amount >= 0 else '-'}${abs(amount):.2f}"


def _signed_percent(value: Any) -> str:
    return f"{float(value or 0.0):+.2f}%"


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
        "source_heading": "Current Source context:",
        "thread_heading": "Thread-local context:",
        "recall_heading": "Semantic recall:",
        "relational_heading": "Current relational state:",
        "relational_modes": {},
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
    source_context: list[str] | None = None,
) -> str:
    harness = prompt_harness_for_agent(agent_id)
    normalized_channel = (channel_name or "").strip().lower()
    normalized_agent = (agent_id or "").strip().lower()
    intro_lines = [
        str(line).strip()
        for line in list(harness.get("intro_lines") or [])
        if str(line).strip()
    ]
    if normalized_channel == "open-communication" and normalized_agent == "discord-clawd":
        intro_lines = [
            "You are c_lawd replying in the #open-communication Discord channel alongside Dali and jeeebs.",
            "This channel is an open forum. Respond directly to the user and the current conversation.",
            "Be concrete, useful, and conversational.",
            "Add a distinct angle from Dali when helpful, but stay on the actual topic being discussed.",
            "Use OPEN_QUESTIONS.md or governance material only when the user is explicitly asking for that layer.",
        ]
    if not intro_lines:
        intro_lines = [
            "You are replying inside a Discord server chat channel.",
            "Respond conversationally and directly to the latest user message.",
        ]
    channel_guidance: list[str] = []
    if normalized_channel == "open-communication":
        channel_guidance = [
            "This channel is an open forum for live conversation between the user and the beings.",
            "Treat the current exchange as primary context.",
            "Use OPEN_QUESTIONS.md or governance material only as supporting context when directly relevant, not as the default frame.",
            "Respond like a participant in the room, not like you are filing a governance memo.",
        ]
        if normalized_agent == "discord-clawd":
            channel_guidance.append(
                "As c_lawd in this channel, stay concrete and conversational; do not let philosophical or governance motifs dominate unless the user explicitly asks for that register."
            )
    lines = [
        *intro_lines,
        f"Harness: {harness.get('name', 'default')}",
        f"Channel: #{channel_name or 'unknown'}",
        f"Author: {author_name or 'unknown'}",
    ]
    if channel_guidance:
        lines.extend(["", *channel_guidance])
    lines.extend([
        "",
        "Latest message:",
        content.strip() or "[no text content]",
    ])
    if source_context is None:
        source_context = source_context_packet_text(limit=6)
    if source_context:
        lines.extend(["", "Current Source context:", *source_context[:6]])
    relational_context = build_relational_prompt_lines(harness=harness, limit=5)
    if relational_context:
        lines.extend(["", str(harness.get("relational_heading") or "Current relational state:").strip(), *relational_context])
    if user_context:
        lines.extend(["", str(harness.get("preference_heading") or "Stable user preferences:").strip(), *user_context[:6]])
    if memory_context:
        lines.extend(["", str(harness.get("memory_heading") or "Relevant prior context:").strip(), *memory_context[:6]])
    if attachments:
        lines.extend(["", str(harness.get("attachment_heading") or "Attachments:").strip()])
        lines.extend(f"- {item}" for item in attachments[:5])
    return "\n".join(lines)


def build_telegram_chat_prompt(
    *,
    agent_id: str | None = None,
    author_name: str,
    chat_title: str,
    content: str,
    memory_context: list[str] | None = None,
    user_context: list[str] | None = None,
    source_context: list[str] | None = None,
    thread_context: list[str] | None = None,
    recall_context: str | None = None,
) -> str:
    harness = prompt_harness_for_agent(agent_id)
    intro_lines = [
        str(line).strip()
        for line in list(harness.get("intro_lines") or [])
        if str(line).strip()
    ]
    if not intro_lines:
        intro_lines = [
            "You are replying inside a Telegram chat.",
            "Respond directly to the latest user message.",
            "Keep the answer concise unless depth is requested.",
        ]
    lines = [
        *intro_lines,
        f"Harness: {harness.get('name', 'default')}",
        "Surface: telegram",
        f"Chat: {chat_title or 'unknown'}",
        f"Author: {author_name or 'unknown'}",
        "",
        "Latest message:",
        content.strip() or "[no text content]",
    ]
    if source_context is None:
        source_context = source_context_packet_text(limit=4, include_preferences=False)
    if source_context:
        lines.extend(["", str(harness.get("source_heading") or "Current Source context:").strip(), *source_context[:4]])
    if user_context:
        lines.extend(["", str(harness.get("preference_heading") or "Stable user preferences:").strip(), *user_context[:6]])
    if thread_context:
        lines.extend(["", str(harness.get("thread_heading") or "Thread-local context:").strip(), *thread_context[:4]])
    if memory_context:
        lines.extend(["", str(harness.get("memory_heading") or "Relevant prior context:").strip(), *memory_context[:6]])
    normalized_recall = str(recall_context or "").strip()
    if normalized_recall:
        lines.extend(["", str(harness.get("recall_heading") or "Semantic recall:").strip(), normalized_recall])
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


def telegram_memory_context_text(
    *,
    chat_id: int | str,
    author_name: str,
    exclude_message_id: int | str | None = None,
    thread_message_id: int | str | None = None,
    limit: int = 4,
) -> list[str]:
    return build_telegram_memory_context(
        chat_id=chat_id,
        author_name=author_name,
        exclude_message_id=exclude_message_id,
        thread_message_id=thread_message_id,
        limit=limit,
    )


def user_context_packet_text(
    limit: int = 4,
    *,
    context: str = "",
    agent_id: str | None = None,
    channel_name: str = "",
) -> list[str]:
    profile_sections: list[str] = []
    normalized_channel = str(channel_name or "").strip().lower()
    normalized_agent = str(agent_id or "").strip().lower()
    if normalized_channel in {"open-communication", "orchestrator"}:
        profile_sections.extend(["communication", "reporting", "verification"])
    if normalized_channel in {"research", "symbiote"}:
        profile_sections.extend(["research", "verification", "tooling"])
    if normalized_agent in {"discord-clawd", "c_lawd"}:
        profile_sections.extend(["communication", "notifications", "reporting"])
    elif normalized_agent in {"discord-orchestrator", "dali", "telegram-dali"}:
        profile_sections.extend(["verification", "tooling", "research"])
    packet = query_preference_graph(
        context=context,
        profile_sections=profile_sections or None,
        limit=limit,
    )
    lines = [str(line).strip() for line in list(packet.get("prompt_lines") or []) if str(line).strip()]
    if lines:
        return lines[: max(1, int(limit))]
    return build_user_context_packet(
        limit=limit,
        context=context,
        profile_sections=profile_sections or None,
    )


def source_context_packet_text(limit: int = 6, *, include_preferences: bool = True) -> list[str]:
    if portfolio_payload is None:
        return []
    try:
        payload = portfolio_payload()
    except Exception:
        return []
    packet = payload.get("context_packet") if isinstance(payload, dict) else None
    if not isinstance(packet, dict):
        return []

    rows: list[str] = []
    for line in packet.get("summary_lines") or []:
        text = str(line).strip()
        if text:
            rows.append(f"- {text}")
    if include_preferences:
        for line in packet.get("preference_lines") or []:
            text = str(line).strip()
            if text:
                rows.append(text if text.startswith("- ") else f"- {text}")
    return rows[: max(1, int(limit))]


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
    review = payload.get("sim_strategy_review") if isinstance(payload.get("sim_strategy_review"), dict) else {}
    recommendations = {
        str(item.get("id") or ""): item
        for item in list(review.get("recommendations") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    if sim_id is None:
        sims = [sim for sim in sims if bool(sim.get("active_book"))]
    lines = ["**Sim Status**"]
    if sim_id is None:
        trade_count = sum(int(sim.get("round_trips", 0) or 0) for sim in sims)
        live_capital = sum(float(sim.get("live_equity", sim.get("final_equity", 0.0)) or 0.0) for sim in sims)
        live_pnl = sum(float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)) or 0.0) for sim in sims)
        open_positions = sum(int(sim.get("open_positions", 0) or 0) for sim in sims)
        lines.append(
            f"- Active book: {len(sims)} sims | {trade_count} trades | capital ${live_capital:.2f} | "
            f"P/L {_signed_currency(live_pnl)} | {open_positions} open"
        )
    for sim in sims[:6]:
        live_equity = float(sim.get("live_equity", sim.get("final_equity", 0.0)) or 0.0)
        live_pnl = float(sim.get("live_equity_change", sim.get("net_equity_change", 0.0)) or 0.0)
        live_return_pct = float(sim.get("live_return_pct", sim.get("net_return_pct", 0.0)) or 0.0)
        label = str(sim.get("display_name") or sim.get("id") or "SIM")
        row = (
            f"- {label}: capital ${live_equity:.2f} | "
            f"P/L {_signed_currency(live_pnl)} ({_signed_percent(live_return_pct)}) | "
            f"trades {int(sim.get('round_trips', 0) or 0)} | "
            f"win {float(sim.get('win_rate', 0.0) or 0.0):.1f}%"
        )
        flags: list[str] = []
        if bool(sim.get("halted")):
            flags.append("halted")
        if bool(sim.get("fee_drag")):
            flags.append("fee drag")
        if int(sim.get("open_positions", 0) or 0) > 0:
            flags.append(f"{int(sim.get('open_positions', 0) or 0)} open")
        if str(sim.get("stage") or "").strip().lower() == "staged":
            flags.append("awaiting feed")
        elif bool(sim.get("control_lane")):
            flags.append("control")
        recommendation = recommendations.get(str(sim.get("id") or ""))
        if isinstance(recommendation, dict):
            rec = str(recommendation.get("recommendation") or "").strip()
            if rec and rec != "keep":
                flags.append(rec)
        if flags:
            row = f"{row} | " + " | ".join(flags)
        lines.append(row)
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
