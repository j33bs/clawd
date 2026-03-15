#!/usr/bin/env python3
"""Backfill Telegram chat history into scoped local memory stores."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.telegram_memory import ingest_telegram_exchange  # type: ignore
from workspace.scripts.telegram_ingest import parse_export_file  # type: ignore

ENV_FILE = Path.home() / ".config" / "openclaw" / "telegram-memory.env"


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _load_normalized_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_openclaw_session_index(path: Path) -> tuple[str | None, str | None]:
    index_path = path.parent / "sessions.json"
    if not index_path.exists():
        return None, None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    session_id = path.stem
    for value in payload.values():
        if not isinstance(value, dict):
            continue
        if str(value.get("sessionId") or "") != session_id:
            continue
        display_name = str(value.get("displayName") or "").strip() or None
        last_to = str(value.get("lastTo") or "").strip()
        chat_id = None
        if last_to.startswith("telegram:"):
            chat_id = last_to.split(":", 1)[1].strip() or None
        return chat_id, display_name
    return None, None


def _extract_openclaw_user_text(raw: str) -> tuple[str, dict[str, Any]]:
    text = str(raw or "")
    meta: dict[str, Any] = {}
    if (
        text.startswith("[cron:")
        or text.startswith("Read HEARTBEAT.md if it exists")
        or text.startswith("Reply with exactly:")
    ):
        return "", {}
    if "Conversation info (untrusted metadata):" not in text:
        return text.strip(), meta

    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    if blocks:
        try:
            convo = json.loads(blocks[0])
            if isinstance(convo, dict):
                meta.update(convo)
        except Exception:
            pass
    if len(blocks) > 1:
        try:
            sender = json.loads(blocks[1])
            if isinstance(sender, dict):
                meta["sender_label"] = sender.get("label")
                meta["sender_username"] = sender.get("username")
                meta["sender_name"] = sender.get("name")
                meta["sender_id"] = sender.get("id", meta.get("sender_id"))
        except Exception:
            pass
    tail = re.split(r"```(?:json)?\s*", text)
    cleaned = text
    if len(tail) >= 5:
        cleaned = tail[-1]
    cleaned = cleaned.replace("```", "").strip()
    return cleaned, meta


def _load_openclaw_session_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    default_chat_id, default_chat_title = _read_openclaw_session_index(path)
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        message = item.get("message")
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "") != "user":
            continue
        text_parts = []
        for part in message.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text") or ""))
        normalized_text, extracted = _extract_openclaw_user_text("\n".join(text_parts))
        if not normalized_text:
            continue
        rows.append(
            {
                "chat_id": str(extracted.get("sender_id") or default_chat_id or ""),
                "chat_title": str(default_chat_title or "telegram-main"),
                "message_id": str(extracted.get("message_id") or item.get("id") or ""),
                "timestamp": str(extracted.get("timestamp") or item.get("timestamp") or ""),
                "sender_id": str(extracted.get("sender_id") or default_chat_id or ""),
                "sender_name": str(extracted.get("sender_name") or "jeebs"),
                "text": normalized_text,
                "source": "openclaw_telegram_session",
                "meta": {
                    "session_id": path.stem,
                    "source_file": str(path),
                },
            }
        )
    return rows


def load_rows(path: Path) -> list[dict[str, Any]]:
    if ".jsonl" in path.name.lower():
        first_line = ""
        try:
            with path.open("r", encoding="utf-8") as handle:
                first_line = handle.readline().strip()
        except Exception:
            first_line = ""
        if '"type":"session"' in first_line or '"type": "session"' in first_line:
            return _load_openclaw_session_jsonl(path)
        return _load_normalized_jsonl(path)
    return parse_export_file(path)


def parse_csv_set(raw: str) -> set[str]:
    return {chunk.strip().lower().lstrip("@") for chunk in str(raw or "").split(",") if chunk.strip()}


def infer_role(
    row: dict[str, Any],
    *,
    self_ids: set[str],
    self_names: set[str],
    assistant_names: set[str],
) -> str:
    sender_id = str(row.get("sender_id") or "").strip()
    sender_name = str(row.get("sender_name") or "").strip().lower().lstrip("@")
    if sender_id and sender_id in self_ids:
        return "user"
    if sender_name and sender_name in self_names:
        return "user"
    if sender_name and sender_name in assistant_names:
        return "assistant"
    return "participant"


def backfill_rows(
    rows: list[dict[str, Any]],
    *,
    allowed_chat_ids: set[str],
    self_ids: set[str],
    self_names: set[str],
    assistant_names: set[str],
    agent_scope: str,
    limit: int | None = None,
) -> dict[str, Any]:
    inserted = 0
    duplicates = 0
    skipped = 0
    processed = 0
    selected = rows if limit is None else rows[: max(0, int(limit))]
    for row in selected:
        processed += 1
        chat_id = str(row.get("chat_id") or "").strip()
        if allowed_chat_ids and chat_id not in allowed_chat_ids:
            skipped += 1
            continue
        result = ingest_telegram_exchange(
            chat_id=chat_id,
            chat_title=str(row.get("chat_title") or "unknown"),
            message_id=str(row.get("message_id") or ""),
            author_id=row.get("sender_id"),
            author_name=str(row.get("sender_name") or "unknown"),
            role=infer_role(
                row,
                self_ids=self_ids,
                self_names=self_names,
                assistant_names=assistant_names,
            ),
            content=str(row.get("text") or ""),
            created_at=str(row.get("timestamp") or ""),
            agent_scope=agent_scope,
            source=str(row.get("source") or "telegram"),
            meta=dict(row.get("meta") or {}),
        )
        if result.get("stored"):
            inserted += 1
        elif result.get("reason") == "dedup":
            duplicates += 1
        else:
            skipped += 1
    return {
        "processed_rows": processed,
        "inserted_rows": inserted,
        "duplicate_rows": duplicates,
        "skipped_rows": skipped,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Telegram export JSON or normalized JSONL path.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    load_env_file()
    args = parse_args()
    rows = load_rows(Path(args.input).resolve())
    summary = backfill_rows(
        rows,
        allowed_chat_ids={chunk.strip() for chunk in os.environ.get("OPENCLAW_TELEGRAM_MEMORY_CHAT_IDS", "").split(",") if chunk.strip()},
        self_ids={chunk.strip() for chunk in os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SELF_IDS", "").split(",") if chunk.strip()},
        self_names=parse_csv_set(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SELF_NAMES", "jeebs")),
        assistant_names=parse_csv_set(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_ASSISTANT_NAMES", "dali,c_lawd,openclaw")),
        agent_scope=os.environ.get("OPENCLAW_TELEGRAM_MEMORY_AGENT_SCOPE", "main").strip() or "main",
        limit=args.limit,
    )
    summary["input_path"] = str(Path(args.input).resolve())
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for key, value in summary.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
