#!/usr/bin/env python3
"""
ITC Pipeline - Telethon Reader
Category: C (Feature)

MTProto user-session based Telegram reader using Telethon.
Capable of reading private groups/chats that Bot API cannot access.

Environment Variables:
- TG_API_ID: Telegram API ID (from https://my.telegram.org)
- TG_API_HASH: Telegram API Hash
- TG_SESSION_PATH: Path to session file (default: .secrets/telethon_itc.session)
- TG_PHONE: Phone number for first-time authentication
- ALLOWED_CHAT_IDS: Comma-separated allowed chat IDs

Usage:
    # First run - authenticate:
    python telegram_reader_telethon.py --auth

    # Run ingestion:
    python telegram_reader_telethon.py --run

    # Dry-run mode:
    python telegram_reader_telethon.py --run --dry-run
"""

import os
import sys
import asyncio
import signal
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel

from itc_pipeline.ingestion_boundary import (
    IngestedMessage,
    ingest_message,
    initialize_ingestion,
    get_dedupe_store
)
from itc_pipeline.allowlist import load_allowlist_from_env

logger = logging.getLogger(__name__)

# Configuration from environment
API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
SESSION_PATH = os.environ.get(
    "TG_SESSION_PATH",
    str(Path(__file__).parent.parent.parent / ".secrets" / "telethon_itc.session")
)
PHONE = os.environ.get("TG_PHONE")

# Graceful shutdown flag
_shutdown_requested = False


def validate_config():
    """Validate required configuration is present."""
    errors = []
    if not API_ID:
        errors.append("TG_API_ID environment variable not set")
    if not API_HASH:
        errors.append("TG_API_HASH environment variable not set")

    if errors:
        for e in errors:
            logger.error(e)
        raise ValueError("Missing required Telegram configuration. See errors above.")


def get_client() -> TelegramClient:
    """Create and return a Telethon client."""
    validate_config()

    # Ensure session directory exists
    session_dir = Path(SESSION_PATH).parent
    session_dir.mkdir(parents=True, exist_ok=True)

    return TelegramClient(SESSION_PATH, int(API_ID), API_HASH)


async def authenticate():
    """
    Interactive authentication flow.
    Run this once to create the session file.
    """
    validate_config()
    client = get_client()

    print("\n" + "=" * 60)
    print("Telethon Authentication")
    print("=" * 60)
    print(f"Session will be saved to: {SESSION_PATH}")
    print()

    await client.start(phone=PHONE)

    me = await client.get_me()
    print(f"\nAuthenticated as: {me.first_name} (@{me.username})")
    print(f"User ID: {me.id}")
    print("\nSession saved. You can now run the ingestion process.")
    print("=" * 60)

    await client.disconnect()


def normalize_message(event) -> Optional[IngestedMessage]:
    """
    Convert a Telethon message event to normalized IngestedMessage.

    Args:
        event: Telethon NewMessage event

    Returns:
        IngestedMessage or None if message should be skipped
    """
    message = event.message

    # Skip non-text messages (for now)
    if not message.text:
        logger.debug(f"Skipping non-text message: {message.id}")
        return None

    # Get chat info
    chat = event.chat
    chat_id = event.chat_id
    chat_title = None

    if isinstance(chat, Channel):
        chat_title = chat.title
    elif isinstance(chat, Chat):
        chat_title = chat.title
    elif isinstance(chat, User):
        chat_title = f"DM: {chat.first_name}"

    # Get sender info
    sender = message.sender
    sender_id = None
    sender_name = None

    if sender:
        sender_id = sender.id
        if isinstance(sender, User):
            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            if sender.username:
                sender_name += f" (@{sender.username})"

    # Build normalized message
    return IngestedMessage(
        source="telegram",
        chat_id=chat_id,
        message_id=message.id,
        date=message.date.astimezone(timezone.utc).isoformat(),
        sender_id=sender_id,
        sender_name=sender_name,
        chat_title=chat_title,
        text=message.text,
        raw_metadata={
            "reply_to_msg_id": message.reply_to_msg_id,
            "forwards": message.forwards,
            "views": message.views,
            "edit_date": message.edit_date.isoformat() if message.edit_date else None,
        }
    )


async def run_ingestion(dry_run: bool = False):
    """
    Main ingestion loop.
    Subscribes to new messages and forwards allowed ones to the pipeline.
    """
    global _shutdown_requested

    validate_config()
    client = get_client()

    # Initialize ingestion boundary (logs allowlist, sets up dedupe)
    initialize_ingestion()

    # Get allowlist for handler
    allowlist = load_allowlist_from_env()

    if not allowlist:
        logger.error(
            "ABORT: Allowlist is empty. No messages would be ingested. "
            "Run telegram_list_dialogs.py first and set ALLOWED_CHAT_IDS."
        )
        return

    logger.info(f"Starting Telethon ingestion (dry_run={dry_run})")
    logger.info(f"Session: {SESSION_PATH}")

    @client.on(events.NewMessage())
    async def handler(event):
        """Handle incoming messages."""
        if _shutdown_requested:
            return

        try:
            # Normalize message
            msg = normalize_message(event)
            if msg is None:
                return

            # Forward to ingestion boundary (handles allowlist, dedupe)
            ingest_message(msg, dry_run=dry_run)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    # Connect and run
    await client.start(phone=PHONE)

    me = await client.get_me()
    logger.info(f"Connected as: {me.first_name} (@{me.username}) [ID: {me.id}]")

    print("\n" + "=" * 60)
    print("Telethon Ingestion Running")
    print("=" * 60)
    print(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print(f"Monitoring {len(allowlist)} allowed chats")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    # Keep running until shutdown
    try:
        while not _shutdown_requested:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

    # Cleanup
    logger.info("Shutting down...")
    get_dedupe_store().save()
    await client.disconnect()
    logger.info("Disconnected from Telegram")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    logger.info(f"Received signal {signum}, requesting shutdown...")
    _shutdown_requested = True


def main():
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ITC Pipeline Telethon Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  TG_API_ID         Telegram API ID (required)
  TG_API_HASH       Telegram API Hash (required)
  TG_SESSION_PATH   Session file path (default: .secrets/telethon_itc.session)
  TG_PHONE          Phone number for authentication
  ALLOWED_CHAT_IDS  Comma-separated allowed chat IDs

Examples:
  # First-time authentication
  python telegram_reader_telethon.py --auth

  # Run ingestion
  python telegram_reader_telethon.py --run

  # Dry-run mode (log only, don't process)
  python telegram_reader_telethon.py --run --dry-run
        """
    )

    parser.add_argument(
        "--auth",
        action="store_true",
        help="Run interactive authentication flow"
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the ingestion process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be ingested without processing"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Reduce Telethon noise
    logging.getLogger("telethon").setLevel(logging.WARNING)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.auth:
        asyncio.run(authenticate())
    elif args.run:
        asyncio.run(run_ingestion(dry_run=args.dry_run))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
