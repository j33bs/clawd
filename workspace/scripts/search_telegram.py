#!/usr/bin/env python3
"""Semantic search CLI for Telegram vector store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from telegram_vector_store import DEFAULT_STORE_DIR, search_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Telegram vector store.")
    parser.add_argument("query")
    parser.add_argument("--chat")
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--after")
    parser.add_argument("--before")
    parser.add_argument("--show-full", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR))
    return parser.parse_args()


def format_result(row: dict, *, show_full: bool) -> dict:
    text = str(row.get("text", ""))
    snippet = text if show_full else text[:200]
    return {
        "score": row.get("_score"),
        "timestamp": row.get("timestamp"),
        "sender_name": row.get("sender_name"),
        "chat_title": row.get("chat_title"),
        "chat_id": row.get("chat_id"),
        "message_id": row.get("message_id"),
        "hash": row.get("hash"),
        "snippet": snippet,
        "text": text if show_full else None,
    }


def main() -> int:
    args = parse_args()
    rows = search_store(
        args.query,
        topk=max(1, int(args.topk)),
        chat_id=args.chat,
        after=args.after,
        before=args.before,
        store_dir=Path(args.store_dir).resolve(),
    )
    formatted = [format_result(row, show_full=bool(args.show_full)) for row in rows]

    if args.json:
        print(json.dumps(formatted, ensure_ascii=True, sort_keys=True))
        return 0

    for idx, row in enumerate(formatted, start=1):
        print(
            f"{idx}. [{row['timestamp']}] {row['sender_name']} ({row['chat_title']}) "
            f"message_id={row['message_id']} hash={row['hash']} score={row['score']}"
        )
        print(f"   {row['snippet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
