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
    # If credentials are missing, you will be prompted for them.

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
import importlib
import getpass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Add repo and workspace roots for direct script execution.
_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (str(_REPO_ROOT), str(_WORKSPACE_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from itc_pipeline.ingestion_boundary import (
    IngestedMessage,
    ingest_message,
    initialize_ingestion,
    get_dedupe_store
)
from itc_pipeline.allowlist import require_allowlist, AllowlistConfigError, ChatNotAllowedError

logger = logging.getLogger(__name__)
MAX_BACKFILL_MESSAGES = 500
DEFAULT_SECRETS_ENV_PATH = _REPO_ROOT / "secrets.env"

# Graceful shutdown flag
_shutdown_requested = False


def _telethon_defaults() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        telethon = importlib.import_module("telethon")
        telethon_errors = importlib.import_module("telethon.errors")
        telethon_types = importlib.import_module("telethon.tl.types")
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("telethon_not_installed: pip install telethon") from exc
    return (
        telethon.TelegramClient,
        telethon.events,
        telethon_errors.FloodWaitError,
        telethon_types.User,
        telethon_types.Chat,
        telethon_types.Channel,
    )


def _runtime_config() -> dict[str, str]:
    return {
        "api_id": str(os.environ.get("TG_API_ID") or "").strip(),
        "api_hash": str(os.environ.get("TG_API_HASH") or "").strip(),
        "session_path": str(
            os.environ.get(
                "TG_SESSION_PATH",
                str(Path(__file__).parent.parent.parent / ".secrets" / "telethon_itc.session"),
            )
        ).strip(),
        "phone": str(os.environ.get("TG_PHONE") or "").strip(),
    }


def _interactive_available() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_value(
    label: str,
    default: str = "",
    secret: bool = False,
    required: bool = True,
    show_default: bool = True,
) -> str:
    while True:
        suffix = f" [{default}]" if default and show_default else ""
        prompt = f"{label}{suffix}: "
        value = getpass.getpass(prompt) if secret else input(prompt)
        value = value.strip()
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        print(f"{label} is required.")


def _persist_runtime_config(config: dict[str, str], path: Path = DEFAULT_SECRETS_ENV_PATH) -> None:
    managed = {
        "TG_API_ID": config["api_id"],
        "TG_API_HASH": config["api_hash"],
        "TG_PHONE": config["phone"],
        "TG_SESSION_PATH": config["session_path"],
    }
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    written = set()
    output_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in managed:
            output_lines.append(f"{key}={managed[key]}")
            written.add(key)
        else:
            output_lines.append(line)

    for key, value in managed.items():
        if key not in written:
            output_lines.append(f"{key}={value}")

    path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")


def resolve_config(
    prompt_if_missing: bool = False,
    require_phone: bool = False,
    force_prompt: bool = False,
) -> dict[str, str]:
    config = _runtime_config()
    missing = []
    if not config["api_id"]:
        missing.append("TG_API_ID")
    if not config["api_hash"]:
        missing.append("TG_API_HASH")
    if require_phone and not config["phone"]:
        missing.append("TG_PHONE")

    if missing and not prompt_if_missing and not force_prompt:
        validate_config(config)
        if require_phone and not config["phone"]:
            raise ValueError("Missing required Telegram configuration. TG_PHONE is required for authentication.")
        return config

    prompted = False
    if missing or force_prompt:
        if not _interactive_available():
            validate_config(config)
            if require_phone and not config["phone"]:
                raise ValueError("Missing required Telegram configuration. TG_PHONE is required for authentication.")
            return config

        print("\nTelegram ITC setup")
        print("=" * 60)
        print("Enter the Telegram app credentials from https://my.telegram.org/apps")
        print("Leave session path blank to use the default.")
        print("=" * 60)
        config["api_id"] = _prompt_value("Telegram API ID", default=config["api_id"], show_default=True)
        config["api_hash"] = _prompt_value(
            "Telegram API hash",
            default=config["api_hash"],
            secret=True,
            show_default=False,
        )
        if require_phone or force_prompt:
            config["phone"] = _prompt_value(
                "Telegram phone number (+countrycode)",
                default=config["phone"],
                show_default=True,
                required=require_phone,
            )
        config["session_path"] = _prompt_value("Session path", default=config["session_path"], required=True)
        prompted = True
    elif prompt_if_missing and require_phone and not config["phone"] and _interactive_available():
        config["phone"] = _prompt_value("Telegram phone number (+countrycode)")
        prompted = True

    validate_config(config)
    if require_phone and not config["phone"]:
        raise ValueError("Missing required Telegram configuration. TG_PHONE is required for authentication.")

    if prompted and _interactive_available():
        choice = input(f"Save Telegram config to {DEFAULT_SECRETS_ENV_PATH}? [Y/n]: ").strip().lower()
        if choice in {"", "y", "yes"}:
            _persist_runtime_config(config)
            print(f"Saved Telegram config to {DEFAULT_SECRETS_ENV_PATH}")

    return config


def validate_config(config: Optional[dict[str, str]] = None):
    """Validate required configuration is present."""
    config = config or _runtime_config()
    errors = []
    if not config["api_id"]:
        errors.append("TG_API_ID environment variable not set")
    if not config["api_hash"]:
        errors.append("TG_API_HASH environment variable not set")

    if errors:
        for e in errors:
            logger.error(e)
        raise ValueError("Missing required Telegram configuration. See errors above.")


def get_client(config: Optional[dict[str, str]] = None):
    """Create and return a Telethon client."""
    config = config or _runtime_config()
    validate_config(config)
    TelegramClient, _, _, _, _, _ = _telethon_defaults()

    # Ensure session directory exists
    session_dir = Path(config["session_path"]).parent
    session_dir.mkdir(parents=True, exist_ok=True)

    return TelegramClient(config["session_path"], int(config["api_id"]), config["api_hash"])


async def authenticate(force_prompt: bool = False):
    """
    Interactive authentication flow.
    Run this once to create the session file.
    """
    config = resolve_config(prompt_if_missing=True, require_phone=True, force_prompt=force_prompt)
    client = get_client(config)

    print("\n" + "=" * 60)
    print("Telethon Authentication")
    print("=" * 60)
    print(f"Session will be saved to: {config['session_path']}")
    print()

    await client.start(phone=config["phone"] or None)

    me = await client.get_me()
    print(f"\nAuthenticated as: {me.first_name} (@{me.username})")
    print(f"User ID: {me.id}")
    print("\nSession saved. You can now run the ingestion process.")
    print("=" * 60)

    await client.disconnect()


async def normalize_message(message: Any, chat: Any = None, chat_id: Optional[int] = None) -> Optional[IngestedMessage]:
    """Convert a Telethon message object to normalized IngestedMessage."""
    _, _, _, User, Chat, Channel = _telethon_defaults()

    if not getattr(message, "text", None):
        logger.debug(f"Skipping non-text message: {getattr(message, 'id', '<unknown>')}")
        return None

    chat = chat or getattr(message, "chat", None)
    if chat is None and hasattr(message, "get_chat"):
        chat = await message.get_chat()
    resolved_chat_id = chat_id if chat_id is not None else getattr(message, "chat_id", None)
    if resolved_chat_id is None and chat is not None:
        resolved_chat_id = getattr(chat, "id", None)

    chat_title = None
    if isinstance(chat, (Channel, Chat)):
        chat_title = getattr(chat, "title", None)
    elif isinstance(chat, User):
        chat_title = f"DM: {chat.first_name}"
    elif chat is not None:
        chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", None)

    sender = getattr(message, "sender", None)
    if sender is None and hasattr(message, "get_sender"):
        sender = await message.get_sender()
    sender_id = getattr(sender, "id", None) if sender is not None else None
    sender_name = None
    if isinstance(sender, User):
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        if getattr(sender, "username", None):
            sender_name += f" (@{sender.username})"
    elif sender is not None:
        sender_name = getattr(sender, "title", None) or getattr(sender, "first_name", None)

    return IngestedMessage(
        source="telegram",
        chat_id=int(resolved_chat_id),
        message_id=message.id,
        date=message.date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        sender_id=sender_id,
        sender_name=sender_name,
        chat_title=chat_title,
        text=message.text,
        raw_metadata={
            "reply_to_msg_id": message.reply_to_msg_id,
            "forwards": message.forwards,
            "views": message.views,
            "edit_date": message.edit_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if message.edit_date
            else None,
        },
    )


async def _backfill_allowed_chats(client: Any, allowlist: set[int], dry_run: bool, limit: int) -> int:
    _, _, FloodWaitError, _, _, _ = _telethon_defaults()
    capped_limit = max(0, min(int(limit or 0), MAX_BACKFILL_MESSAGES))
    if capped_limit <= 0:
        return 0

    ingested = 0
    for chat_id in sorted(allowlist):
        try:
            entity = await client.get_entity(chat_id)
            logger.info(f"Backfilling chat_id={chat_id} title={getattr(entity, 'title', None)!r} limit={capped_limit}")
            async for raw_message in client.iter_messages(entity, limit=capped_limit):
                normalized = await normalize_message(raw_message, chat=entity, chat_id=chat_id)
                if normalized is None:
                    continue
                if ingest_message(normalized, dry_run=dry_run):
                    ingested += 1
        except FloodWaitError as exc:  # pragma: no cover - depends on Telegram runtime
            logger.warning(f"FloodWait while backfilling chat_id={chat_id}; sleeping {exc.seconds}s")
            await asyncio.sleep(exc.seconds + 1)
        except ChatNotAllowedError:
            raise
        except Exception as exc:
            logger.error(f"Failed backfill for chat_id={chat_id}: {exc}", exc_info=True)
    return ingested


async def run_ingestion(
    dry_run: bool = False,
    backfill_limit: int = 0,
    exit_after_backfill: bool = False,
    force_prompt: bool = False,
):
    """
    Main ingestion loop.
    Subscribes to new messages and forwards allowed ones to the pipeline.
    """
    global _shutdown_requested

    config = resolve_config(prompt_if_missing=True, require_phone=False, force_prompt=force_prompt)
    client = get_client(config)
    _, events, _, _, _, _ = _telethon_defaults()

    # Initialize ingestion boundary (logs allowlist, sets up dedupe)
    initialize_ingestion()

    # Get allowlist for handler
    try:
        allowlist = require_allowlist()
    except AllowlistConfigError as exc:
        logger.error(str(exc))
        return

    logger.info(f"Starting Telethon ingestion (dry_run={dry_run})")
    logger.info(f"Session: {config['session_path']}")

    @client.on(events.NewMessage(chats=list(allowlist)))
    async def handler(event):
        """Handle incoming messages."""
        if _shutdown_requested:
            return

        try:
            # Normalize message
            msg = await normalize_message(event.message, chat=event.chat, chat_id=event.chat_id)
            if msg is None:
                return
            if msg.chat_id not in allowlist:
                raise ChatNotAllowedError(msg.chat_id, msg.chat_title)

            # Forward to ingestion boundary (handles allowlist, dedupe)
            ingest_message(msg, dry_run=dry_run)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    # Connect and run
    await client.start(phone=config["phone"] or None)

    me = await client.get_me()
    logger.info(f"Connected as: {me.first_name} (@{me.username}) [ID: {me.id}]")

    if backfill_limit:
        ingested = await _backfill_allowed_chats(client, allowlist, dry_run=dry_run, limit=backfill_limit)
        logger.info(f"Backfill complete: {ingested} messages accepted")
        if exit_after_backfill:
            logger.info("Exiting after backfill (--once)")
            get_dedupe_store().save()
            await client.disconnect()
            return

    print("\n" + "=" * 60)
    print("Telethon Ingestion Running")
    print("=" * 60)
    print(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print(f"Monitoring {len(allowlist)} allowed chats")
    if backfill_limit:
        print(f"Backfill: {min(int(backfill_limit), MAX_BACKFILL_MESSAGES)} messages per allowed chat")
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
  # Missing API ID / hash / phone will be prompted interactively
  python telegram_reader_telethon.py --auth --reconfigure

  # Run ingestion
  python telegram_reader_telethon.py --run

  # Backfill then continue listening
  python telegram_reader_telethon.py --run --backfill 100

  # Backfill and exit
  python telegram_reader_telethon.py --once --backfill 100

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
        "--once",
        action="store_true",
        help="Backfill then exit without starting the live listener"
    )
    parser.add_argument(
        "--backfill",
        type=int,
        default=0,
        help=f"Backfill N recent messages per allowed chat (max {MAX_BACKFILL_MESSAGES})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be ingested without processing"
    )
    parser.add_argument(
        "--reconfigure",
        action="store_true",
        help="Prompt for Telegram credentials even if they already exist"
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
        asyncio.run(authenticate(force_prompt=args.reconfigure))
    elif args.run or args.once:
        asyncio.run(
            run_ingestion(
                dry_run=args.dry_run,
                backfill_limit=args.backfill,
                exit_after_backfill=args.once,
                force_prompt=args.reconfigure,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
