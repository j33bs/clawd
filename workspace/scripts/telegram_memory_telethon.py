#!/usr/bin/env python3
"""Live Telegram memory listener with optional backfill for personal chats."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import signal
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_UI_ROOT = REPO_ROOT / "workspace" / "source-ui"
for path in (SOURCE_UI_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from api.telegram_memory import ingest_telegram_exchange  # type: ignore
from workspace.itc_pipeline.telegram_reader_telethon import (  # type: ignore
    MAX_BACKFILL_MESSAGES,
    _telethon_defaults,
    get_client,
    normalize_message,
    resolve_config,
)

ENV_FILE = Path.home() / ".config" / "openclaw" / "telegram-memory.env"
DEFAULT_ALLOWLIST_PATH = Path.home() / ".openclaw" / "credentials" / "telegram-default-allowFrom.json"
DEFAULT_ENV_FILES = (
    REPO_ROOT / "secrets.env",
    Path.home() / ".openclaw" / "secrets.env",
    ENV_FILE,
)

logger = logging.getLogger(__name__)
_shutdown_requested = False


def _load_simple_env(path: Path) -> None:
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


def load_env_file(path: Path = ENV_FILE) -> None:
    _load_simple_env(path)


def bootstrap_environment() -> None:
    for env_file in DEFAULT_ENV_FILES:
        _load_simple_env(env_file)


def parse_csv_set(raw: str) -> set[str]:
    return {chunk.strip().lower().lstrip("@") for chunk in str(raw or "").split(",") if chunk.strip()}


def _name_candidates(raw: Any) -> set[str]:
    text = str(raw or "").strip().lower()
    if not text:
        return set()
    candidates = {text.lstrip("@")}
    stripped = re.sub(r"\s*\(@[^)]+\)\s*", "", text).strip()
    if stripped:
        candidates.add(stripped.lstrip("@"))
    for username in re.findall(r"@([a-z0-9_]+)", text):
        candidates.add(username.lower().lstrip("@"))
    return {item for item in candidates if item}


def resolve_chat_allowlist() -> set[int]:
    raw = os.environ.get("OPENCLAW_TELEGRAM_MEMORY_CHAT_IDS", "").strip()
    if raw:
        values = set()
        for chunk in raw.split(","):
            text = chunk.strip()
            if not text:
                continue
            values.add(int(text))
        return values

    path = Path(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_ALLOWLIST_PATH", str(DEFAULT_ALLOWLIST_PATH)))
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    values = payload.get("allow_chat_ids")
    if not isinstance(values, list):
        values = payload.get("allowFrom", [])
    allowed: set[int] = set()
    if isinstance(values, list):
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            try:
                allowed.add(int(text))
            except ValueError:
                continue
    return allowed


def infer_role(chat_row: Any, *, self_ids: set[str], self_names: set[str], assistant_names: set[str]) -> str:
    sender_id = str(getattr(chat_row, "sender_id", None) or "").strip()
    sender_names = _name_candidates(getattr(chat_row, "sender_name", None))
    if sender_id and sender_id in self_ids:
        return "user"
    if sender_names.intersection(self_names):
        return "user"
    if sender_names.intersection(assistant_names):
        return "assistant"
    return "participant"


def _canonical_chat_id(normalized: Any, *, self_ids: set[str]) -> int | str:
    chat_title = str(getattr(normalized, "chat_title", "") or "")
    if chat_title.startswith("DM:") and self_ids:
        try:
            return int(sorted(self_ids)[0])
        except ValueError:
            return sorted(self_ids)[0]
    return getattr(normalized, "chat_id", "")


def ingest_normalized_message(
    normalized: Any,
    *,
    self_ids: set[str],
    self_names: set[str],
    assistant_names: set[str],
    agent_scope: str,
) -> dict[str, Any]:
    canonical_chat_id = _canonical_chat_id(normalized, self_ids=self_ids)
    return ingest_telegram_exchange(
        chat_id=canonical_chat_id,
        chat_title=str(normalized.chat_title or "unknown"),
        message_id=normalized.message_id,
        author_id=normalized.sender_id,
        author_name=str(normalized.sender_name or "unknown"),
        role=infer_role(
            normalized,
            self_ids=self_ids,
            self_names=self_names,
            assistant_names=assistant_names,
        ),
        content=str(normalized.text or ""),
        created_at=str(normalized.date or ""),
        agent_scope=agent_scope,
        source=str(normalized.source or "telegram"),
        meta=dict(normalized.raw_metadata or {}),
    )


async def _backfill_allowed_chats(
    client: Any,
    allowlist: set[int],
    *,
    limit: int,
    self_ids: set[str],
    self_names: set[str],
    assistant_names: set[str],
    agent_scope: str,
) -> dict[str, int]:
    _, _, FloodWaitError, _, _, _ = _telethon_defaults()
    capped_limit = max(0, min(int(limit or 0), MAX_BACKFILL_MESSAGES))
    inserted = 0
    duplicates = 0
    skipped = 0
    if capped_limit <= 0:
        return {"inserted": 0, "duplicates": 0, "skipped": 0}
    for chat_id in sorted(allowlist):
        try:
            entity = await client.get_entity(chat_id)
            logger.info("Telegram memory backfill: chat_id=%s limit=%s", chat_id, capped_limit)
            async for raw_message in client.iter_messages(entity, limit=capped_limit):
                normalized = await normalize_message(raw_message, chat=entity, chat_id=chat_id)
                if normalized is None:
                    skipped += 1
                    continue
                result = ingest_normalized_message(
                    normalized,
                    self_ids=self_ids,
                    self_names=self_names,
                    assistant_names=assistant_names,
                    agent_scope=agent_scope,
                )
                if result.get("stored"):
                    inserted += 1
                elif result.get("reason") == "dedup":
                    duplicates += 1
                else:
                    skipped += 1
        except FloodWaitError as exc:  # pragma: no cover
            logger.warning("FloodWait while backfilling chat_id=%s; sleeping %ss", chat_id, exc.seconds)
            await asyncio.sleep(exc.seconds + 1)
        except Exception as exc:
            logger.error("Failed Telegram memory backfill for chat_id=%s: %s", chat_id, exc, exc_info=True)
    return {"inserted": inserted, "duplicates": duplicates, "skipped": skipped}


async def run_listener(*, backfill_limit: int = 0, keep_running: bool = True) -> int:
    global _shutdown_requested
    bootstrap_environment()
    allowlist = resolve_chat_allowlist()
    if not allowlist:
        logger.error("No Telegram memory chat IDs configured.")
        return 2

    self_ids = {chunk.strip() for chunk in os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SELF_IDS", "").split(",") if chunk.strip()}
    self_names = parse_csv_set(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SELF_NAMES", "jeebs"))
    assistant_names = parse_csv_set(os.environ.get("OPENCLAW_TELEGRAM_MEMORY_ASSISTANT_NAMES", "dali,c_lawd,openclaw"))
    agent_scope = os.environ.get("OPENCLAW_TELEGRAM_MEMORY_AGENT_SCOPE", "main").strip() or "main"

    config = resolve_config(prompt_if_missing=False, require_phone=False, force_prompt=False)
    session_override = os.environ.get("OPENCLAW_TELEGRAM_MEMORY_SESSION_PATH", "").strip()
    if session_override:
        os.environ["TG_SESSION_PATH"] = session_override
        config["session_path"] = session_override
    client = get_client(config)
    _, events, _, _, _, _ = _telethon_defaults()

    @client.on(events.NewMessage(chats=list(allowlist)))
    async def handler(event: Any) -> None:
        if _shutdown_requested:
            return
        try:
            normalized = await normalize_message(event.message, chat=event.chat, chat_id=event.chat_id)
            if normalized is None:
                return
            result = ingest_normalized_message(
                normalized,
                self_ids=self_ids,
                self_names=self_names,
                assistant_names=assistant_names,
                agent_scope=agent_scope,
            )
            if result.get("stored"):
                logger.info("Telegram memory ingest ok: chat_id=%s message_id=%s", normalized.chat_id, normalized.message_id)
        except Exception as exc:
            logger.error("Telegram memory handler failed: %s", exc, exc_info=True)

    await client.start(phone=config.get("phone") or None)
    me = await client.get_me()
    logger.info("Telegram memory connected as: %s (%s)", getattr(me, "first_name", "unknown"), getattr(me, "id", "unknown"))

    if backfill_limit:
        report = await _backfill_allowed_chats(
            client,
            allowlist,
            limit=backfill_limit,
            self_ids=self_ids,
            self_names=self_names,
            assistant_names=assistant_names,
            agent_scope=agent_scope,
        )
        logger.info("Telegram memory backfill complete: %s", report)

    if not keep_running:
        await client.disconnect()
        return 0

    logger.info("Telegram memory listener active for %s chats", len(allowlist))
    try:
        while not _shutdown_requested:
            await asyncio.sleep(1)
    finally:
        await client.disconnect()
    return 0


def _signal_handler(signum: int, _frame: Any) -> None:
    global _shutdown_requested
    logger.info("Received signal %s; shutting down Telegram memory listener", signum)
    _shutdown_requested = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", type=int, default=0)
    parser.add_argument("--once", action="store_true", help="Backfill only, then exit.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    if args.once:
        return int(asyncio.run(run_listener(backfill_limit=args.backfill, keep_running=False)))
    return int(asyncio.run(run_listener(backfill_limit=args.backfill, keep_running=True)))


if __name__ == "__main__":
    raise SystemExit(main())
