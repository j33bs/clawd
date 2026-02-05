#!/usr/bin/env python3
"""
ITC Pipeline - Allowlist Gate
Category: B (Security) + C (Feature)

Hard allowlist enforcement at ingestion boundary.
Only messages from explicitly allowed chat IDs pass through.

Configuration:
- Environment variable ALLOWED_CHAT_IDS (comma-separated integers)
- Or direct configuration via ALLOWED_CHAT_IDS_DEFAULT constant

Target chats (by numeric ID - must be discovered via telegram_list_dialogs.py):
- ITC Lifetime Lounge
- Into the Cryptoverse Chat (Private)
- Into the Cryptoverse Alerts (Private)
- Into The Cryptocosm Alerts (Private)

Exclusions (never ingest):
- responder, Mbresponder/Mresponder, BotFather
"""

import os
import logging
from typing import Set, Optional

logger = logging.getLogger(__name__)

# Default allowlist - MUST be populated after running telegram_list_dialogs.py
# Format: Set of integer chat IDs
# Example: {-1001234567890, -1009876543210}
ALLOWED_CHAT_IDS_DEFAULT: Set[int] = set()

# Known exclusions (bot/internal chats to never ingest)
# These are blocked even if somehow in allowlist
EXCLUDED_PATTERNS = {
    "responder",
    "mbresponder",
    "mresponder",
    "botfather",
}


def load_allowlist_from_env() -> Set[int]:
    """
    Load allowed chat IDs from ALLOWED_CHAT_IDS environment variable.

    Returns:
        Set of allowed chat IDs as integers.
        Falls back to ALLOWED_CHAT_IDS_DEFAULT if env var not set.
    """
    env_value = os.environ.get("ALLOWED_CHAT_IDS", "").strip()

    if not env_value:
        logger.warning(
            "ALLOWED_CHAT_IDS not set in environment. "
            "Using default allowlist (may be empty)."
        )
        return ALLOWED_CHAT_IDS_DEFAULT.copy()

    allowed = set()
    for part in env_value.split(","):
        part = part.strip()
        if part:
            try:
                chat_id = int(part)
                allowed.add(chat_id)
            except ValueError:
                logger.error(f"Invalid chat_id in ALLOWED_CHAT_IDS: '{part}' (not an integer)")

    return allowed


def is_chat_allowed(
    chat_id: int,
    chat_title: Optional[str] = None,
    allowlist: Optional[Set[int]] = None
) -> bool:
    """
    Check if a chat is allowed for ingestion.

    This is the HARD GATE - messages from non-allowed chats are dropped.

    Args:
        chat_id: Numeric Telegram chat ID (peer_id)
        chat_title: Optional chat title for logging/exclusion check
        allowlist: Optional explicit allowlist (defaults to env-loaded list)

    Returns:
        True if chat is allowed, False otherwise
    """
    # Load allowlist if not provided
    if allowlist is None:
        allowlist = load_allowlist_from_env()

    # Check exclusion patterns first (by title)
    if chat_title:
        title_lower = chat_title.lower()
        for pattern in EXCLUDED_PATTERNS:
            if pattern in title_lower:
                logger.debug(
                    f"DROP: chat_id={chat_id} title='{chat_title}' "
                    f"matched exclusion pattern '{pattern}'"
                )
                return False

    # Hard allowlist check by chat_id
    if chat_id not in allowlist:
        logger.debug(
            f"DROP: chat_id={chat_id} title='{chat_title or 'N/A'}' "
            f"not in allowlist ({len(allowlist)} entries)"
        )
        return False

    # Passed all gates
    logger.info(
        f"ACCEPT: chat_id={chat_id} title='{chat_title or 'N/A'}' "
        f"passed allowlist gate"
    )
    return True


def log_allowlist_on_startup():
    """
    Log the current allowlist configuration on startup.
    Call this when starting the ingestion process.
    """
    allowlist = load_allowlist_from_env()

    logger.info("=" * 60)
    logger.info("ITC Pipeline - Allowlist Configuration")
    logger.info("=" * 60)
    logger.info(f"Allowed chat IDs: {len(allowlist)} entries")

    for chat_id in sorted(allowlist):
        logger.info(f"  - {chat_id}")

    if not allowlist:
        logger.warning(
            "WARNING: Allowlist is EMPTY. No messages will be ingested. "
            "Run telegram_list_dialogs.py to discover chat IDs."
        )

    logger.info(f"Excluded patterns: {EXCLUDED_PATTERNS}")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Test allowlist loading
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    log_allowlist_on_startup()
