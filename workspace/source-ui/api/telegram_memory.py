"""Telegram chat memory ingestion into local HiveMind + knowledge graph."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
KB_DATA_DIR = REPO_ROOT / "workspace" / "knowledge_base" / "data"
TELEGRAM_MEMORY_PATH = KB_DATA_DIR / "telegram_messages.jsonl"
TELEGRAM_MEMORY_STATE_PATH = KB_DATA_DIR / "telegram_memory_ingest_state.json"

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


def _load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    keys = payload.get("processed_keys") if isinstance(payload, dict) else []
    if not isinstance(keys, list):
        return set()
    return {str(item) for item in keys if str(item).strip()}


def _save_state(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "updated_at": _now_iso(),
        "processed_keys": sorted(keys),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _memory_key(chat_id: int | str, message_id: int | str) -> str:
    return f"{chat_id}:{message_id}"


def _memory_text(record: dict[str, Any]) -> str:
    lines = [
        f"Telegram {record.get('role', 'message')} in {record.get('chat_title', 'unknown chat')}",
        f"Chat id: {record.get('chat_id', 'unknown')}",
        f"Author: {record.get('author_name', 'unknown')} ({record.get('author_id', 'unknown')})",
        f"Created at: {record.get('created_at', '')}",
        f"Message id: {record.get('message_id', '')}",
    ]
    raw_meta = dict(record.get("meta") or {})
    if raw_meta:
        lines.append("Metadata:")
        for key in sorted(raw_meta)[:8]:
            lines.append(f"- {key}: {raw_meta.get(key)}")
    lines.extend(["", "Content:", str(record.get("content", "")).strip() or "[no text content]"])
    return "\n".join(lines).strip()


def ingest_telegram_exchange(
    *,
    chat_id: int | str,
    chat_title: str,
    message_id: int | str,
    author_id: int | str | None,
    author_name: str,
    role: str,
    content: str,
    created_at: str | None = None,
    agent_scope: str = "main",
    source: str = "telegram",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_content = str(content or "").strip()
    if not normalized_content:
        return {"stored": False, "reason": "empty"}

    dedupe_key = _memory_key(chat_id, message_id)
    known = _load_state(TELEGRAM_MEMORY_STATE_PATH)
    if dedupe_key in known:
        return {"stored": False, "reason": "dedup", "memory_key": dedupe_key}

    record = {
        "schema_version": 1,
        "stored_at": _now_iso(),
        "created_at": str(created_at or _now_iso()),
        "chat_id": str(chat_id),
        "chat_title": str(chat_title or "unknown"),
        "message_id": str(message_id),
        "author_id": str(author_id) if author_id is not None else None,
        "author_name": str(author_name or "unknown"),
        "role": str(role or "participant"),
        "content": normalized_content,
        "agent_scope": str(agent_scope or "main"),
        "source": str(source or "telegram"),
        "meta": dict(meta or {}),
    }
    _append_jsonl(TELEGRAM_MEMORY_PATH, record)
    known.add(dedupe_key)
    _save_state(TELEGRAM_MEMORY_STATE_PATH, known)

    memory_text = _memory_text(record)
    metadata = {
        "chat_id": record["chat_id"],
        "chat_title": record["chat_title"],
        "message_id": record["message_id"],
        "author_id": record["author_id"],
        "author_name": record["author_name"],
        "role": record["role"],
        "source": record["source"],
    }

    hive_store = HiveMindStore()
    ku = KnowledgeUnit(
        kind="telegram_message",
        source=f"telegram:{record['chat_title']}",
        agent_scope=str(agent_scope or "main"),
        ttl_days=None,
        metadata=metadata,
    )
    hive_result = hive_store.put(ku, memory_text)

    graph_store = KnowledgeGraphStore(KB_DATA_DIR)
    graph_id = graph_store.add_entity(
        name=f"telegram:{record['chat_id']}:{record['message_id']}",
        entity_type="telegram_message",
        content=memory_text,
        source=f"telegram:{record['chat_title']}",
        metadata=metadata,
    )

    return {
        "stored": True,
        "jsonl_path": str(TELEGRAM_MEMORY_PATH),
        "memory_key": dedupe_key,
        "hivemind": hive_result,
        "graph_entity_id": graph_id,
    }


def build_telegram_memory_context(
    *,
    chat_id: int | str,
    author_name: str,
    limit: int = 4,
    exclude_message_id: int | str | None = None,
) -> list[str]:
    if not TELEGRAM_MEMORY_PATH.exists():
        return []
    try:
        rows = TELEGRAM_MEMORY_PATH.read_text(encoding="utf-8").splitlines()
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
        row_chat_id = str(row.get("chat_id") or "")
        row_author = str(row.get("author_name") or "").strip().lower()
        if row_chat_id != str(chat_id) and row_author != target_author:
            continue
        text = _compact(str(row.get("content") or ""))
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(
            f"- {str(row.get('created_at') or '')[:10]} {row.get('chat_title', 'unknown')}: {text}"
        )
        if len(selected) >= max(1, int(limit)):
            break
    return list(reversed(selected))
