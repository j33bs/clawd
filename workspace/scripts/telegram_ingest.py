#!/usr/bin/env python3
"""Normalize Telegram export JSON into strict JSONL records."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("workspace/state_runtime/ingest/telegram_normalized/messages.jsonl")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any) -> str:
    if value is None:
        return "1970-01-01T00:00:00Z"
    text = str(value).strip()
    if not text:
        return "1970-01-01T00:00:00Z"
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "1970-01-01T00:00:00Z"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    parsed = parsed.astimezone(dt.timezone.utc).replace(microsecond=0)
    return parsed.isoformat().replace("+00:00", "Z")


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                segment = item.get("text")
                if isinstance(segment, str):
                    parts.append(segment)
        return "".join(parts)
    return ""


def stable_hash(parts: list[str]) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_message(chat: dict[str, Any], message: dict[str, Any], source_path: Path) -> dict[str, Any] | None:
    text = flatten_text(message.get("text", ""))
    text = text.strip()
    if not text:
        return None

    chat_id = str(chat.get("id") if chat.get("id") is not None else chat.get("name", "unknown_chat"))
    message_id = message.get("id")
    message_id_text = str(message_id if message_id is not None else "unknown_message")
    timestamp = parse_timestamp(message.get("date"))
    sender_id = message.get("from_id")
    sender_id_text = str(sender_id) if sender_id is not None else None
    sender_name = message.get("from")
    sender_name_text = str(sender_name) if sender_name is not None else None
    reply_to_message_id = message.get("reply_to_message_id")
    reply_to_value = str(reply_to_message_id) if reply_to_message_id is not None else None

    content_hash = stable_hash(
        [
            chat_id,
            message_id_text,
            timestamp,
            sender_name_text or "",
            text,
        ]
    )

    return {
        "source": "telegram_export",
        "chat_id": chat_id,
        "chat_title": str(chat.get("name") or chat.get("title")) if (chat.get("name") or chat.get("title")) else None,
        "message_id": message_id_text,
        "timestamp": timestamp,
        "sender_id": sender_id_text,
        "sender_name": sender_name_text,
        "text": text,
        "text_len": len(text),
        "reply_to_message_id": reply_to_value,
        "meta": {
            "message_type": str(message.get("type") or "message"),
            "chat_type": str(chat.get("type") or "private"),
            "source_file": str(source_path),
            "ingested_at": utc_now_iso(),
        },
        "hash": content_hash,
    }


def parse_export_file(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    chats = raw.get("chats", {}).get("list", [])
    if not isinstance(chats, list):
        return []

    out: list[dict[str, Any]] = []
    for chat in chats:
        if not isinstance(chat, dict):
            continue
        messages = chat.get("messages")
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            normalized = normalize_message(chat, message, path)
            if normalized is not None:
                out.append(normalized)
    return out


def discover_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = sorted(p for p in path.rglob("*.json") if p.is_file())
    return files


def load_existing_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row_hash = str(row.get("hash", "")).strip()
        if row_hash:
            rows[row_hash] = row
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda item: (str(item.get("timestamp", "")), str(item.get("hash", ""))))
    with path.open("w", encoding="utf-8") as fh:
        for row in ordered:
            fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def ingest_exports(input_path: Path, output_path: Path) -> dict[str, Any]:
    files = discover_input_files(input_path)
    existing = load_existing_rows(output_path)

    parsed_count = 0
    inserted_count = 0
    for file_path in files:
        parsed = parse_export_file(file_path)
        parsed_count += len(parsed)
        for row in parsed:
            row_hash = row["hash"]
            if row_hash in existing:
                continue
            existing[row_hash] = row
            inserted_count += 1

    rows = list(existing.values())
    write_jsonl(output_path, rows)
    return {
        "input_path": str(input_path),
        "files_scanned": len(files),
        "parsed_rows": parsed_count,
        "total_rows": len(rows),
        "inserted_rows": inserted_count,
        "output_path": str(output_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Telegram export JSON into normalized JSONL.")
    parser.add_argument("--input", required=True, help="Path to Telegram export JSON file or directory.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = ingest_exports(Path(args.input).resolve(), Path(args.output).resolve())
    if args.json:
        print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    else:
        print(f"input_path={summary['input_path']}")
        print(f"files_scanned={summary['files_scanned']}")
        print(f"parsed_rows={summary['parsed_rows']}")
        print(f"inserted_rows={summary['inserted_rows']}")
        print(f"total_rows={summary['total_rows']}")
        print(f"output_path={summary['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
