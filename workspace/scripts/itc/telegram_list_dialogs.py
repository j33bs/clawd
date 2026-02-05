#!/usr/bin/env python3
"""
ITC Pipeline - Telegram Dialog Listing Utility
Category: D (Documentation/Tooling)

Lists all Telegram dialogs (chats, groups, channels) with their numeric IDs.
Use this to discover the correct chat_ids for the allowlist.

Output:
- Console: Human-readable list
- File: tmp/telegram_dialogs.tsv (tab-separated)

Usage:
    python telegram_list_dialogs.py

Environment Variables:
    TG_API_ID       Telegram API ID (required)
    TG_API_HASH     Telegram API Hash (required)
    TG_SESSION_PATH Session file path
"""

import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel

# Configuration
API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
SESSION_PATH = os.environ.get(
    "TG_SESSION_PATH",
    str(Path(__file__).parent.parent.parent.parent / ".secrets" / "telethon_itc.session")
)

OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "tmp"
OUTPUT_FILE = OUTPUT_DIR / "telegram_dialogs.tsv"


def validate_config():
    """Validate required configuration."""
    if not API_ID:
        print("ERROR: TG_API_ID environment variable not set")
        sys.exit(1)
    if not API_HASH:
        print("ERROR: TG_API_HASH environment variable not set")
        sys.exit(1)


def get_entity_type(entity) -> str:
    """Get human-readable entity type."""
    if isinstance(entity, User):
        if entity.bot:
            return "Bot"
        return "User"
    elif isinstance(entity, Chat):
        return "Group"
    elif isinstance(entity, Channel):
        if entity.megagroup:
            return "Supergroup"
        if entity.broadcast:
            return "Channel"
        return "Channel"
    return "Unknown"


async def list_dialogs():
    """List all dialogs and output to console and file."""
    validate_config()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)

    print("\n" + "=" * 80)
    print("Telegram Dialog Listing")
    print("=" * 80)
    print(f"Session: {SESSION_PATH}")
    print()

    await client.start()

    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username}) [ID: {me.id}]")
    print()

    # Collect dialogs
    dialogs = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        entity_type = get_entity_type(entity)

        # Get username if available
        username = getattr(entity, 'username', None) or ""

        # Get title/name
        if isinstance(entity, User):
            title = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
        else:
            title = getattr(entity, 'title', str(entity.id))

        dialogs.append({
            "chat_id": dialog.id,
            "title": title,
            "username": username,
            "type": entity_type,
            "unread_count": dialog.unread_count,
        })

    # Sort by type, then title
    type_order = {"Supergroup": 0, "Group": 1, "Channel": 2, "User": 3, "Bot": 4, "Unknown": 5}
    dialogs.sort(key=lambda d: (type_order.get(d["type"], 5), d["title"].lower()))

    # Print to console
    print(f"{'TYPE':<12} {'CHAT_ID':<20} {'TITLE':<40} {'USERNAME':<20}")
    print("-" * 92)

    for d in dialogs:
        print(f"{d['type']:<12} {d['chat_id']:<20} {d['title'][:40]:<40} @{d['username']:<19}")

    print("-" * 92)
    print(f"Total: {len(dialogs)} dialogs")
    print()

    # Write to TSV file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("type\tchat_id\ttitle\tusername\tunread_count\n")
        for d in dialogs:
            f.write(f"{d['type']}\t{d['chat_id']}\t{d['title']}\t{d['username']}\t{d['unread_count']}\n")

    print(f"Output written to: {OUTPUT_FILE}")
    print()

    # Highlight ITC-related chats
    itc_keywords = ["itc", "cryptoverse", "cryptocosm", "lounge"]
    itc_matches = []

    for d in dialogs:
        title_lower = d["title"].lower()
        if any(kw in title_lower for kw in itc_keywords):
            itc_matches.append(d)

    if itc_matches:
        print("=" * 80)
        print("POTENTIAL ITC CHATS DETECTED:")
        print("=" * 80)
        for d in itc_matches:
            print(f"  {d['type']:<12} chat_id={d['chat_id']:<20} {d['title']}")
        print()
        print("To use these, set ALLOWED_CHAT_IDS environment variable:")
        ids = ",".join(str(d["chat_id"]) for d in itc_matches)
        print(f"  export ALLOWED_CHAT_IDS=\"{ids}\"")
        print()

    # Filter for target chats
    target_names = [
        "itc lifetime lounge",
        "into the cryptoverse chat",
        "into the cryptoverse alerts",
        "into the cryptocosm alerts",
    ]

    target_matches = []
    for d in dialogs:
        title_lower = d["title"].lower()
        for target in target_names:
            if target in title_lower:
                target_matches.append(d)
                break

    if target_matches:
        print("=" * 80)
        print("TARGET CHATS FOUND (from specification):")
        print("=" * 80)
        for d in target_matches:
            print(f"  chat_id={d['chat_id']:<20} {d['title']}")
        print()
        print("Recommended ALLOWED_CHAT_IDS:")
        ids = ",".join(str(d["chat_id"]) for d in target_matches)
        print(f"  export ALLOWED_CHAT_IDS=\"{ids}\"")
        print()
        print("Or add to secrets.env:")
        print(f"  ALLOWED_CHAT_IDS={ids}")
        print("=" * 80)

    await client.disconnect()


def main():
    """CLI entrypoint."""
    asyncio.run(list_dialogs())


if __name__ == "__main__":
    main()
