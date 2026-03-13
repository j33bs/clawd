"""Discord chat memory ingestion into local HiveMind + knowledge graph."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
KB_DATA_DIR = REPO_ROOT / "workspace" / "knowledge_base" / "data"
DISCORD_MEMORY_PATH = KB_DATA_DIR / "discord_messages.jsonl"
DISCORD_RESEARCH_PATH = KB_DATA_DIR / "discord_research_messages.jsonl"

import sys

HIVEMIND_ROOT = REPO_ROOT / "workspace" / "hivemind"
KB_ROOT = REPO_ROOT / "workspace" / "knowledge_base"
for path in (HIVEMIND_ROOT, KB_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from hivemind.models import KnowledgeUnit  # type: ignore
from hivemind.store import HiveMindStore  # type: ignore
from graph.store import KnowledgeGraphStore  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _compact(text: str, *, limit: int = 600) -> str:
    value = " ".join(str(text or "").split()).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _memory_text(record: dict[str, Any]) -> str:
    attachments = list(record.get("attachments") or [])
    lines = [
        f"Discord {record.get('role', 'message')} in #{record.get('channel_name', 'unknown')}",
        f"Guild: {record.get('guild_name', 'unknown')}",
        f"Author: {record.get('author_name', 'unknown')} ({record.get('author_id', 'unknown')})",
        f"Created at: {record.get('created_at', '')}",
        f"Message id: {record.get('message_id', '')}",
        f"Channel id: {record.get('channel_id', '')}",
    ]
    if record.get("agent_id"):
        lines.append(f"Agent: {record.get('agent_id')}")
    if attachments:
        lines.append("Attachments:")
        lines.extend(f"- {item}" for item in attachments[:5])
    lines.extend(["", "Content:", str(record.get("content", "")).strip() or "[no text content]"])
    return "\n".join(lines).strip()


def _research_text(record: dict[str, Any]) -> str:
    lines = [
        f"Discord research-channel {record.get('role', 'message')} in #{record.get('channel_name', 'unknown')}",
        f"Guild: {record.get('guild_name', 'unknown')}",
        f"Author: {record.get('author_name', 'unknown')} ({record.get('author_id', 'unknown')})",
        f"Created at: {record.get('created_at', '')}",
        f"Message id: {record.get('message_id', '')}",
    ]
    if record.get("agent_id"):
        lines.append(f"Agent: {record.get('agent_id')}")
    lines.extend(["", "Content:", str(record.get("content", "")).strip() or "[no text content]"])
    return "\n".join(lines).strip()


def ingest_discord_exchange(
    *,
    guild_id: int | None,
    guild_name: str,
    channel_id: int,
    channel_name: str,
    message_id: int | str,
    author_id: int | str | None,
    author_name: str,
    role: str,
    content: str,
    attachments: list[str] | None = None,
    created_at: str | None = None,
    agent_scope: str = "main",
    agent_id: str = "",
    ingest_research: bool = False,
) -> dict[str, Any]:
    normalized_content = str(content or "").strip()
    attachment_rows = [str(item).strip() for item in (attachments or []) if str(item).strip()]
    if not normalized_content and not attachment_rows:
        return {"stored": False, "reason": "empty"}

    record = {
        "schema_version": 1,
        "stored_at": _now_iso(),
        "created_at": str(created_at or _now_iso()),
        "guild_id": int(guild_id) if guild_id is not None else None,
        "guild_name": str(guild_name or "unknown"),
        "channel_id": int(channel_id),
        "channel_name": str(channel_name or "unknown"),
        "message_id": str(message_id),
        "author_id": str(author_id) if author_id is not None else None,
        "author_name": str(author_name or "unknown"),
        "role": str(role or "user"),
        "content": normalized_content,
        "attachments": attachment_rows,
        "agent_id": str(agent_id or ""),
        "agent_scope": str(agent_scope or "main"),
    }
    _append_jsonl(DISCORD_MEMORY_PATH, record)

    memory_text = _memory_text(record)
    metadata = {
        "guild_id": record["guild_id"],
        "guild_name": record["guild_name"],
        "channel_id": record["channel_id"],
        "channel_name": record["channel_name"],
        "message_id": record["message_id"],
        "author_id": record["author_id"],
        "author_name": record["author_name"],
        "role": record["role"],
        "agent_id": record["agent_id"],
    }

    hive_store = HiveMindStore()
    ku = KnowledgeUnit(
        kind="discord_message",
        source=f"discord:{record['channel_name']}",
        agent_scope=str(agent_scope or "main"),
        ttl_days=None,
        metadata=metadata,
    )
    hive_result = hive_store.put(ku, memory_text)

    graph_store = KnowledgeGraphStore(KB_DATA_DIR)
    graph_id = graph_store.add_entity(
        name=f"discord:{record['channel_name']}:{record['message_id']}",
        entity_type="discord_message",
        content=memory_text,
        source=f"discord:{record['channel_name']}",
        metadata=metadata,
    )

    result = {
        "stored": True,
        "jsonl_path": str(DISCORD_MEMORY_PATH),
        "hivemind": hive_result,
        "graph_entity_id": graph_id,
    }
    if ingest_research and normalized_content:
        _append_jsonl(DISCORD_RESEARCH_PATH, record)
        research_graph_id = graph_store.add_entity(
            name=f"discord-research:{record['channel_name']}:{record['message_id']}",
            entity_type="discord_research_message",
            content=_research_text(record),
            source=f"discord-research:{record['channel_name']}",
            metadata={**metadata, "research_channel": True},
        )
        result["research"] = {
            "stored": True,
            "jsonl_path": str(DISCORD_RESEARCH_PATH),
            "graph_entity_id": research_graph_id,
        }
    return result


def build_discord_memory_context(
    *,
    channel_id: int,
    author_name: str,
    limit: int = 4,
    exclude_message_id: int | None = None,
) -> list[str]:
    if not DISCORD_MEMORY_PATH.exists():
        return []
    try:
        rows = DISCORD_MEMORY_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    target_author = str(author_name or "").strip().lower()
    selected: list[str] = []
    seen: set[str] = set()
    for raw in reversed(rows):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        if exclude_message_id is not None and str(row.get("message_id", "")) == str(exclude_message_id):
            continue
        if str(row.get("role") or "") != "user":
            continue
        row_channel_id = int(row.get("channel_id", 0) or 0)
        row_author = str(row.get("author_name") or "").strip().lower()
        if row_channel_id != int(channel_id) and row_author != target_author:
            continue
        text = _compact(str(row.get("content") or ""))
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            f"- {str(row.get('created_at') or '')[:10]} #{row.get('channel_name', 'unknown')}: {text}"
        )
        if len(selected) >= max(1, int(limit)):
            break
    return list(reversed(selected))
