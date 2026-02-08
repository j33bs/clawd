#!/usr/bin/env python3
"""
Telethon Telegram Ingester
Reads messages from configured Telegram channels and appends to itc/raw/telegram.jsonl.

CBP Safeguards:
  1. READ-ONLY: Never sends messages, joins channels, or modifies remote state.
  2. RATE-LIMITED: Respects Telethon FloodWaitError; backs off automatically.
  3. ALLOWLISTED: Only ingests from chats explicitly listed in pipeline config.
  4. PROVENANCE: Every raw record includes ingestion metadata for audit trail.

Requires: TELETHON_API_ID and TELETHON_API_HASH in secrets.env or system env
First run: python scripts/telethon_auth.py (interactive, creates session file)
Then:      python scripts/telethon_ingest.py [--once] [--backfill N]
"""

import json
import time
import asyncio
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from telethon import TelegramClient, events
    from telethon.errors import FloodWaitError
except ImportError:
    print("ERROR: telethon not installed. Run: pip install telethon")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

BASE_DIR = Path("C:/Users/heath/.openclaw")
CONFIG_PATH = BASE_DIR / "pipelines" / "system1_trading.yaml"
SECRETS_PATH = BASE_DIR / "secrets.env"
SESSION_DIR = BASE_DIR / "secrets" / "telethon"
RAW_OUT = BASE_DIR / "itc" / "raw" / "telegram.jsonl"
ITC_PIPELINE_DIR = BASE_DIR / "workspace" / "itc_pipeline"

if ITC_PIPELINE_DIR.exists():
    sys.path.insert(0, str(ITC_PIPELINE_DIR.parent))
    try:
        from itc_pipeline.allowlist import (
            require_allowlist,
            assert_chat_allowed,
            AllowlistConfigError,
            ChatNotAllowedError,
        )
    except Exception:
        require_allowlist = None
        def assert_chat_allowed(*args, **kwargs):
            return None
        class AllowlistConfigError(RuntimeError):
            pass
        class ChatNotAllowedError(RuntimeError):
            pass
else:
    require_allowlist = None
    def assert_chat_allowed(*args, **kwargs):
        return None
    class AllowlistConfigError(RuntimeError):
        pass
    class ChatNotAllowedError(RuntimeError):
        pass

# ── Rate limiting ───────────────────────────────────────────────
RATE_DELAY_SECONDS = 1.0        # delay between entity resolutions
BACKFILL_BATCH_PAUSE = 0.5      # pause between message batches
MAX_BACKFILL_PER_CHANNEL = 500  # hard cap regardless of --backfill flag


def load_secrets():
    """Read key=value pairs from secrets.env (skip comments, blanks)."""
    secrets = {}
    if not SECRETS_PATH.exists():
        return secrets
    with open(SECRETS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()
    return secrets


def load_config():
    """Load pipeline YAML config."""
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def build_allowlist(chats_config):
    """Build the set of allowed chat name patterns from config.
    Only channels explicitly listed here will be ingested."""
    allowed = set()
    for chat_cfg in chats_config:
        allowed.add(chat_cfg["name"].lower())
        for m in chat_cfg.get("match", []):
            allowed.add(m.lower())
    return allowed


def write_raw(event_data):
    """Append one JSON line to the raw output file."""
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_data, ensure_ascii=False) + "\n")


def serialize_event(message):
    """Turn a Telethon message into a flat dict safe for JSONL.
    Includes provenance fields for audit trail."""
    return {
        "ts": int(message.date.timestamp() * 1000),
        "ingested_at": int(time.time() * 1000),
        "ingester": "telethon_ingest.py",
        "chat_id": message.chat_id,
        "chat_title": getattr(message.chat, "title", None) or str(message.chat_id),
        "msg_id": message.id,
        "sender_id": message.sender_id,
        "text": message.raw_text or "",
        "has_media": message.media is not None,
        "reply_to": message.reply_to_msg_id if message.reply_to_msg_id else None,
        "fwd_from": bool(message.fwd_from),
    }


async def resolve_entity_safe(client, pattern):
    """Resolve a chat entity with FloodWait handling."""
    try:
        entity = await client.get_entity(pattern)
        await asyncio.sleep(RATE_DELAY_SECONDS)
        return entity
    except FloodWaitError as e:
        print(f"  FloodWait: sleeping {e.seconds}s (Telegram rate limit)")
        await asyncio.sleep(e.seconds + 1)
        return await client.get_entity(pattern)


async def backfill(client, chats, limit, allowlist, allowlist_ids=None):
    """Fetch the last `limit` messages per channel. Allowlist-gated."""
    limit = min(limit, MAX_BACKFILL_PER_CHANNEL)
    total = 0
    for chat_cfg in chats:
        name = chat_cfg["name"]
        matches = chat_cfg.get("match", [name])
        chan_count = 0
        for pattern in matches:
            try:
                entity = await resolve_entity_safe(client, pattern)
                entity_title = getattr(entity, "title", str(entity.id)).lower()

                # ── Allowlist gate ──────────────────────────────
                if not any(a in entity_title or entity_title in a for a in allowlist):
                    if pattern.lower() not in allowlist:
                        print(f"  [{name}] BLOCKED: '{entity_title}' not in allowlist, skipping")
                        break
                if allowlist_ids is not None and assert_chat_allowed is not None:
                    assert_chat_allowed(entity.id, entity_title, allowlist_ids)

                async for msg in client.iter_messages(entity, limit=limit):
                    if msg.raw_text:
                        write_raw(serialize_event(msg))
                        chan_count += 1
                    # Pace the iteration
                    if chan_count % 50 == 0 and chan_count > 0:
                        await asyncio.sleep(BACKFILL_BATCH_PAUSE)

                total += chan_count
                print(f"  [{name}] backfilled {chan_count} messages")
                break  # matched on first pattern
            except FloodWaitError as e:
                print(f"  [{name}] FloodWait: sleeping {e.seconds}s")
                await asyncio.sleep(e.seconds + 1)
            except ChatNotAllowedError as e:
                print(str(e))
                raise
            except Exception as e:
                print(f"  [{name}] pattern '{pattern}' failed: {e}")
    return total


async def listen(client, chats, allowlist, allowlist_ids=None):
    """Live-listen for new messages in configured channels. Allowlist-gated."""
    chat_ids = set()
    for chat_cfg in chats:
        matches = chat_cfg.get("match", [chat_cfg["name"]])
        for pattern in matches:
            try:
                entity = await resolve_entity_safe(client, pattern)
                entity_title = getattr(entity, "title", str(entity.id)).lower()

                # ── Allowlist gate ──────────────────────────────
                if not any(a in entity_title or entity_title in a for a in allowlist):
                    if pattern.lower() not in allowlist:
                        print(f"  BLOCKED: '{entity_title}' not in allowlist")
                        break
                if allowlist_ids is not None and assert_chat_allowed is not None:
                    assert_chat_allowed(entity.id, entity_title, allowlist_ids)

                chat_ids.add(entity.id)
                print(f"  Listening: {chat_cfg['name']} (id={entity.id})")
                break
            except FloodWaitError as e:
                print(f"  FloodWait: sleeping {e.seconds}s")
                await asyncio.sleep(e.seconds + 1)
            except ChatNotAllowedError as e:
                print(str(e))
                raise
            except Exception as e:
                print(f"  Could not resolve {pattern}: {e}")

    if not chat_ids:
        print("ERROR: No channels resolved. Check config and auth.")
        return

    @client.on(events.NewMessage(chats=list(chat_ids)))
    async def handler(event):
        if event.message.raw_text:
            data = serialize_event(event.message)
            write_raw(data)
            print(f"  [{data['chat_title']}] msg {data['msg_id']}")

    print("Live listening (read-only)... (Ctrl+C to stop)")
    await client.run_until_disconnected()


async def main():
    parser = argparse.ArgumentParser(description="Telethon ITC ingester (read-only)")
    parser.add_argument("--once", action="store_true", help="Backfill and exit")
    parser.add_argument("--backfill", type=int, default=100,
                        help=f"Messages per channel (max {MAX_BACKFILL_PER_CHANNEL})")
    args = parser.parse_args()

    secrets = load_secrets()
    api_id = secrets.get("TELETHON_API_ID") or os.environ.get("TELETHON_API_ID")
    api_hash = secrets.get("TELETHON_API_HASH") or os.environ.get("TELETHON_API_HASH")

    if not api_id or not api_hash:
        print("ERROR: TELETHON_API_ID and TELETHON_API_HASH must be set in secrets.env")
        print("Get them from https://my.telegram.org/apps")
        print("Then run: python scripts/telethon_auth.py")
        sys.exit(1)

    config = load_config()
    chats = config["telegram"]["chats"]
    allowlist = build_allowlist(chats)
    allowlist_ids = None
    if require_allowlist is not None:
        try:
            allowlist_ids = require_allowlist()
        except AllowlistConfigError as e:
            print(str(e))
            sys.exit(1)

    print(f"Allowlist: {sorted(allowlist)}")

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_path = str(SESSION_DIR / "itc_reader")

    # ── Read-only client ────────────────────────────────────────
    # receive_updates=True is needed for live listening but the client
    # never calls send_message, join_channel, or any write method.
    client = TelegramClient(session_path, int(api_id), api_hash)
    await client.start()

    if not await client.is_user_authorized():
        print("ERROR: Not authorized. Run: python scripts/telethon_auth.py")
        await client.disconnect()
        sys.exit(1)

    me = await client.get_me()
    print(f"Authenticated as: {me.first_name} (read-only mode)")
    print(f"Channels: {[c['name'] for c in chats]}")

    try:
        n = await backfill(client, chats, args.backfill, allowlist, allowlist_ids)
        print(f"Backfill complete: {n} messages written to {RAW_OUT}")

        if not args.once:
            await listen(client, chats, allowlist, allowlist_ids)
        else:
            await client.disconnect()
    except ChatNotAllowedError as e:
        print(str(e))
        await client.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
