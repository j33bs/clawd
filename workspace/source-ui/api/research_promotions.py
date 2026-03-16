"""Research-message promotion helpers for Source UI."""

from __future__ import annotations

from typing import Any

from .task_store import (
    DISCORD_RESEARCH_PATH,
    RESEARCH_PROMOTION_ORIGIN,
    TASKS_PATH,
    _normalize_source_links,
    _normalize_task_kind,
    _normalize_task_priority,
    _normalize_task_status,
    _read_jsonl,
    _slug,
    _trim,
    create_task,
    load_tasks,
)


def _research_rows(*, research_path=DISCORD_RESEARCH_PATH, limit: int = 120) -> list[dict[str, Any]]:
    rows = _read_jsonl(research_path, limit=max(1, int(limit)))
    return [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("role") or "").strip().lower() == "user" and row.get("content")
    ]


def _research_source_ref(row: dict[str, Any]) -> str:
    guild_id = str(row.get("guild_id") or "").strip()
    channel_id = str(row.get("channel_id") or "").strip()
    message_id = str(row.get("message_id") or "").strip()
    if guild_id and channel_id and message_id:
        return f"discord:{guild_id}:{channel_id}:{message_id}"
    return f"discord:{message_id or _slug(str(row.get('content') or 'research'))}"


def _research_item_id(row: dict[str, Any]) -> str:
    message_id = str(row.get("message_id") or "").strip()
    if message_id:
        return message_id
    return _slug(
        f"{row.get('created_at') or row.get('stored_at') or 'research'}-{row.get('content') or 'research'}"
    )


def _research_item_href(research_id: str) -> str:
    return f"/api/research/items/{str(research_id or '').strip()}"


def _task_research_promotions(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    promoted: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        source_links = _normalize_source_links(task.get("source_links"))
        research_item_id = str(task.get("research_item_id") or "").strip()
        target_ids = {
            str(link.get("id") or "").strip()
            for link in source_links
            if str(link.get("id") or "").strip()
        }
        if research_item_id:
            target_ids.add(research_item_id)
        if not target_ids:
            continue
        entry = {
            "task_id": str(task.get("id") or "").strip(),
            "title": str(task.get("title") or "").strip(),
            "status": _normalize_task_status(task.get("status")),
            "assignee": str(task.get("assignee") or "").strip(),
            "task_kind": _normalize_task_kind(task.get("task_kind")),
        }
        for target_id in target_ids:
            promoted.setdefault(target_id, []).append(entry)
    return promoted


def _build_research_item(row: dict[str, Any], promotions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    research_id = _research_item_id(row)
    source_ref = _research_source_ref(row)
    promotion_rows = [dict(item) for item in (promotions or []) if isinstance(item, dict)]
    channel_name = str(row.get("channel_name") or "research").strip() or "research"
    return {
        "id": research_id,
        "message_id": str(row.get("message_id") or "").strip(),
        "author_name": str(row.get("author_name") or "").strip(),
        "channel_name": channel_name,
        "created_at": str(row.get("created_at") or row.get("stored_at") or "").strip(),
        "content": str(row.get("content") or "").strip(),
        "excerpt": _trim(str(row.get("content") or "").strip(), limit=160),
        "source_ref": source_ref,
        "source_links": [
            {
                "id": research_id,
                "label": f"discord research · #{channel_name}",
                "href": _research_item_href(research_id),
                "ref": source_ref,
            }
        ],
        "promotion_count": len(promotion_rows),
        "promotions": promotion_rows[:3],
    }


def list_research_items(
    *,
    limit: int = 8,
    tasks: list[dict[str, Any]] | None = None,
    tasks_path=TASKS_PATH,
    research_path=DISCORD_RESEARCH_PATH,
) -> list[dict[str, Any]]:
    task_rows = tasks if isinstance(tasks, list) else load_tasks(tasks_path)
    promoted = _task_research_promotions(task_rows)
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in reversed(_research_rows(research_path=research_path, limit=max(24, int(limit) * 8))):
        research_id = _research_item_id(row)
        if research_id in seen_ids:
            continue
        seen_ids.add(research_id)
        items.append(_build_research_item(row, promoted.get(research_id, [])))
        if len(items) >= max(1, int(limit)):
            break
    return items


def get_research_item(
    research_id: str,
    *,
    tasks: list[dict[str, Any]] | None = None,
    tasks_path=TASKS_PATH,
    research_path=DISCORD_RESEARCH_PATH,
) -> dict[str, Any] | None:
    target = str(research_id or "").strip()
    if not target:
        return None
    task_rows = tasks if isinstance(tasks, list) else load_tasks(tasks_path)
    promoted = _task_research_promotions(task_rows)
    for row in reversed(_research_rows(research_path=research_path, limit=500)):
        candidate_id = _research_item_id(row)
        if candidate_id != target:
            continue
        return _build_research_item(row, promoted.get(candidate_id, []))
    return None


def _default_research_promotion_title(item: dict[str, Any], task_kind: str) -> str:
    prefix = "Experiment" if task_kind == "experiment" else "Research follow-up"
    return _trim(f"{prefix}: {item.get('excerpt') or item.get('content') or 'research item'}", limit=96)


def _default_research_promotion_description(item: dict[str, Any]) -> str:
    source_ref = str(item.get("source_ref") or "").strip()
    source_link = ""
    source_links = item.get("source_links") if isinstance(item.get("source_links"), list) else []
    if source_links and isinstance(source_links[0], dict):
        source_link = str(source_links[0].get("href") or "").strip()
    parts = [
        "Promoted from Discord research.",
        "",
        str(item.get("content") or "").strip(),
        "",
        f"Source ref: {source_ref}" if source_ref else "",
        f"Source link: {source_link}" if source_link else "",
    ]
    return "\n".join(part for part in parts if part != "")


def promote_research_item(
    data: dict[str, Any],
    *,
    path=TASKS_PATH,
    research_path=DISCORD_RESEARCH_PATH,
) -> dict[str, Any]:
    research_id = str(data.get("research_id") or data.get("message_id") or "").strip()
    if not research_id:
        raise ValueError("research_id_required")
    assignee = str(data.get("assignee") or "").strip()
    if not assignee:
        raise ValueError("assignee_required")

    item = get_research_item(research_id, tasks_path=path, research_path=research_path)
    if not isinstance(item, dict):
        raise ValueError("research_item_not_found")

    task_kind = _normalize_task_kind(data.get("task_kind"))
    title = str(data.get("title") or "").strip() or _default_research_promotion_title(item, task_kind)
    description = str(data.get("description") or "").strip() or _default_research_promotion_description(item)
    priority = _normalize_task_priority(data.get("priority"))
    project = str(data.get("project") or "").strip()
    task = create_task(
        {
            "title": title,
            "description": description,
            "status": "backlog",
            "priority": priority,
            "assignee": assignee,
            "project": project,
            "origin": RESEARCH_PROMOTION_ORIGIN,
            "task_kind": task_kind,
            "research_item_id": item["id"],
            "source_refs": [str(item.get("source_ref") or "").strip()],
            "source_links": item.get("source_links") or [],
            "source_excerpt": str(item.get("excerpt") or "").strip(),
        },
        path=path,
    )
    return {
        "ok": True,
        "task": task,
        "research_item": get_research_item(item["id"], tasks_path=path, research_path=research_path),
    }
