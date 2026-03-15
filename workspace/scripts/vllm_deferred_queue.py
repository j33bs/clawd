#!/usr/bin/env python3
"""Durable local-vLLM deferral state for fishtank/work mode transitions."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _resolve_repo_root(start: Path) -> Path:
    current = start
    for _ in range(8):
        if (current / ".git").exists():
            return current
        current = current.parent
    return start.parents[2]


REPO_ROOT = _resolve_repo_root(Path(__file__).resolve())
STATE_DIR = REPO_ROOT / "workspace" / "state_runtime" / "vllm_deferred"
STATE_PATH = STATE_DIR / "queue_state.json"
ENV_FILE = Path.home() / ".config" / "openclaw" / "dali-fishtank.env"
VALID_ITC_TAGS = {"trade_signal", "news", "noise", "spam"}
MAX_ENTRIES = 240


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"version": 1, "updated_at": None, "entries": []}
    entries = payload.get("entries")
    if not isinstance(entries, list):
        payload["entries"] = []
    return payload


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    entries = [item for item in list(state.get("entries") or []) if isinstance(item, dict)]
    trimmed = entries[:MAX_ENTRIES]
    payload = {
        "version": 1,
        "updated_at": utc_now_iso(),
        "entries": trimmed,
    }
    _write_json_atomic(path, payload)


def read_mode_profile(env_file: Path = ENV_FILE) -> str:
    if not env_file.exists():
        return "unknown"
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return "unknown"
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DALI_FISHTANK_MODE_PROFILE":
            profile = value.strip()
            return profile or "unknown"
    return "unknown"


def should_defer_local_vllm(profile: str | None = None) -> bool:
    enabled = str(os.environ.get("OPENCLAW_VLLM_DEFER_IN_FISHTANK", "1") or "1").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return False
    return str(profile or read_mode_profile()).strip().lower() == "fishtank"


def _new_entry_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:6]}"


def _extract_prompt_excerpt(payload: dict[str, Any]) -> str:
    for key in ("prompt", "message", "input_text", "content"):
        value = payload.get(key)
        if value:
            text = " ".join(str(value).split())
            return text[:180]
    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("content"):
                text = " ".join(str(item.get("content")).split())
                return text[:180]
    return ""


def summarize_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = state if isinstance(state, dict) else load_state()
    entries = [item for item in list(payload.get("entries") or []) if isinstance(item, dict)]
    deferred = [item for item in entries if str(item.get("status") or "") == "deferred"]
    review = [item for item in entries if str(item.get("status") or "") == "review_required"]
    completed = [item for item in entries if str(item.get("status") or "") == "completed"]
    failed = [item for item in entries if str(item.get("status") or "") == "failed"]
    discord_pending = [item for item in deferred if str(item.get("kind") or "") == "discord_message"]
    router_pending = [item for item in deferred if str(item.get("kind") or "") == "router_request"]
    return {
        "total": len(entries),
        "deferred": len(deferred),
        "review_required": len(review),
        "completed": len(completed),
        "failed": len(failed),
        "discord_pending": len(discord_pending),
        "router_pending": len(router_pending),
        "updated_at": payload.get("updated_at"),
    }


def _upsert_entry(entry: dict[str, Any], *, path: Path = STATE_PATH) -> dict[str, Any]:
    state = load_state(path)
    existing = [
        item
        for item in list(state.get("entries") or [])
        if isinstance(item, dict) and str(item.get("id") or "") != str(entry.get("id") or "")
    ]
    state["entries"] = [entry, *existing]
    save_state(state, path)
    return entry


def enqueue_router_request(
    *,
    intent: str,
    payload: dict[str, Any],
    context_metadata: dict[str, Any] | None,
    provider: str,
    model: str | None,
    capability_class: str,
    request_id: str,
    reason_code: str = "deferred_fishtank",
    path: Path = STATE_PATH,
) -> dict[str, Any]:
    state = load_state(path)
    for item in list(state.get("entries") or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("request_id") or "") != str(request_id):
            continue
        if str(item.get("status") or "") == "deferred":
            return item

    context = dict(context_metadata or {})
    entry = {
        "id": _new_entry_id("router"),
        "kind": "router_request",
        "status": "deferred",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "request_id": str(request_id),
        "intent": str(intent or ""),
        "provider": str(provider or ""),
        "model": str(model or ""),
        "capability_class": str(capability_class or ""),
        "reason_code": str(reason_code or "deferred_fishtank"),
        "resume_policy": str(context.get("deferred_resume_policy") or "review"),
        "source": str(context.get("source_surface") or intent or "router"),
        "prompt_excerpt": _extract_prompt_excerpt(payload),
        "payload": payload,
        "context_metadata": context,
    }
    state["entries"] = [entry, *[item for item in list(state.get("entries") or []) if isinstance(item, dict)]]
    save_state(state, path)
    return entry


def enqueue_discord_message(
    *,
    guild_id: int | None,
    channel_id: int,
    message_id: int,
    author_name: str,
    agent_ids: list[str],
    attachments: list[str],
    open_forum: bool,
    reason_code: str = "deferred_fishtank",
    path: Path = STATE_PATH,
) -> dict[str, Any]:
    state = load_state(path)
    existing = find_entry(kind="discord_message", message_id=message_id, state=state)
    if existing and str(existing.get("status") or "") == "deferred":
        return existing
    entry = {
        "id": _new_entry_id("discord"),
        "kind": "discord_message",
        "status": "deferred",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "reason_code": str(reason_code or "deferred_fishtank"),
        "guild_id": int(guild_id) if guild_id is not None else None,
        "channel_id": int(channel_id),
        "message_id": int(message_id),
        "author_name": str(author_name or ""),
        "agent_ids": [str(item) for item in agent_ids if str(item).strip()],
        "attachments": [str(item) for item in attachments if str(item).strip()],
        "open_forum": bool(open_forum),
        "attempts": 0,
    }
    state["entries"] = [entry, *[item for item in list(state.get("entries") or []) if isinstance(item, dict)]]
    save_state(state, path)
    return entry


def list_entries(
    *,
    kind: str | None = None,
    status: str | None = None,
    limit: int = 20,
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = state if isinstance(state, dict) else load_state()
    rows: list[dict[str, Any]] = []
    for item in list(payload.get("entries") or []):
        if not isinstance(item, dict):
            continue
        if kind and str(item.get("kind") or "") != str(kind):
            continue
        if status and str(item.get("status") or "") != str(status):
            continue
        rows.append(item)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def find_entry(
    *,
    entry_id: str | None = None,
    kind: str | None = None,
    message_id: int | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload = state if isinstance(state, dict) else load_state()
    for item in list(payload.get("entries") or []):
        if not isinstance(item, dict):
            continue
        if entry_id and str(item.get("id") or "") != str(entry_id):
            continue
        if kind and str(item.get("kind") or "") != str(kind):
            continue
        if message_id is not None and int(item.get("message_id", 0) or 0) != int(message_id):
            continue
        return item
    return None


def update_entry(entry_id: str, **updates: Any) -> dict[str, Any] | None:
    state = load_state()
    target = find_entry(entry_id=entry_id, state=state)
    if target is None:
        return None
    updated = {
        **target,
        **updates,
        "updated_at": utc_now_iso(),
    }
    state["entries"] = [
        updated if str(item.get("id") or "") == str(entry_id) else item
        for item in list(state.get("entries") or [])
        if isinstance(item, dict)
    ]
    save_state(state)
    return updated


def validator_for_key(key: str | None):
    value = str(key or "").strip().lower()
    if value == "itc_classify_tag":
        return lambda text: text if str(text or "").strip().lower() in VALID_ITC_TAGS else None
    return None

