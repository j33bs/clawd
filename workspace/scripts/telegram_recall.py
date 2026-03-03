#!/usr/bin/env python3
"""Telegram semantic recall context loader for c_lawd message ingress."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from telegram_vector_store import DEFAULT_STORE_DIR, search_store


DEFAULT_TOPK = 6
DEFAULT_MAX_CHARS = 6000


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def parse_positive_int(value: str | None, default: int) -> int:
    if value is None or not str(value).strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def extract_keyphrases(query: str, max_terms: int = 3) -> list[str]:
    stop = {
        "remember",
        "about",
        "where",
        "which",
        "could",
        "would",
        "should",
        "there",
        "their",
        "after",
        "before",
        "while",
        "discussed",
    }
    counts: dict[str, int] = {}
    for token in re.findall(r"[a-zA-Z0-9_]{4,}", query.lower()):
        if token in stop:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:max(1, max_terms)]]


def should_trigger_recall(prompt: str, *, session_start: bool = False, env: Mapping[str, str] | None = None) -> bool:
    env_map = env if env is not None else os.environ
    enabled = parse_bool(env_map.get("OPENCLAW_TELEGRAM_RECALL"), False)
    if not enabled:
        return False
    if session_start:
        return True
    lowered = prompt.lower()
    triggers = ("remember", "we discussed", "we talked", "did we", "when did we")
    return any(needle in lowered for needle in triggers)


def _row_to_line(row: dict, per_line_limit: int = 1000) -> str:
    text = str(row.get("text", "")).strip().replace("\n", " ")
    if len(text) > per_line_limit:
        text = text[: per_line_limit - 1] + "…"
    ts = str(row.get("timestamp", "unknown-time"))
    sender = str(row.get("sender_name") or "unknown-sender")
    return f"- [{ts}] {sender}: {text}"


def build_recall_block(
    prompt: str,
    *,
    env: Mapping[str, str] | None = None,
    session_start: bool = False,
    store_dir: Path = DEFAULT_STORE_DIR,
) -> str:
    env_map = env if env is not None else os.environ
    if not should_trigger_recall(prompt, session_start=session_start, env=env_map):
        return ""

    topk = parse_positive_int(env_map.get("OPENCLAW_TELEGRAM_RECALL_TOPK"), DEFAULT_TOPK)
    max_chars = parse_positive_int(env_map.get("OPENCLAW_TELEGRAM_RECALL_MAX_CHARS"), DEFAULT_MAX_CHARS)
    chat_filter = env_map.get("OPENCLAW_TELEGRAM_RECALL_CHAT_ID")

    rows = search_store(prompt, topk=topk, chat_id=chat_filter or None, store_dir=Path(store_dir))
    for phrase in extract_keyphrases(prompt):
        extra = search_store(phrase, topk=max(1, topk // 2), chat_id=chat_filter or None, store_dir=Path(store_dir))
        rows.extend(extra)

    deduped: dict[str, dict] = {}
    for row in rows:
        row_hash = str(row.get("hash", ""))
        if not row_hash:
            continue
        if row_hash not in deduped:
            deduped[row_hash] = row

    ordered = sorted(deduped.values(), key=lambda item: str(item.get("timestamp", "")), reverse=True)[:topk]
    if not ordered:
        return ""

    lines = ["TELEGRAM_RECALL:"]
    total = len(lines[0]) + 1
    for row in ordered:
        line = _row_to_line(row)
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def inject_telegram_recall_context(
    prompt: str,
    *,
    env: Mapping[str, str] | None = None,
    session_start: bool = False,
    store_dir: Path = DEFAULT_STORE_DIR,
) -> str:
    recall = build_recall_block(prompt, env=env, session_start=session_start, store_dir=store_dir)
    if not recall:
        return prompt
    return f"{recall}\n\n{prompt}"

