#!/usr/bin/env python3
"""
ITC Pipeline - Allowlist Gate
Category: B (Security) + C (Feature)

Hard allowlist enforcement at ingestion boundary.
Only messages from explicitly allowed chat IDs pass through.

Configuration:
- Environment variable ALLOWED_CHAT_IDS (comma-separated integers)
- Or credentials/telegram-allowFrom.json (fallback)
- Preferred JSON key: allow_chat_ids (array of ints)
- Legacy JSON key: allowFrom (array, parsed as ints with warning)
- Or direct configuration via ALLOWED_CHAT_IDS_DEFAULT constant (last resort)

Target chats (by numeric ID - must be discovered via telegram_list_dialogs.py):
- ITC Lifetime Lounge
- Into the Cryptoverse Chat (Private)
- Into the Cryptoverse Alerts (Private)
- Into The Cryptocosm Alerts (Private)

Exclusions (never ingest):
- responder, Mbresponder/Mresponder, BotFather
"""

import os
import json
import logging
from pathlib import Path
from typing import Set, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Default allowlist - MUST be populated after running telegram_list_dialogs.py
# Format: Set of integer chat IDs
# Example: {-1001234567890, -1009876543210}
ALLOWED_CHAT_IDS_DEFAULT: Set[int] = set()

# Default allowlist file (credentials/telegram-allowFrom.json)
ALLOWLIST_FILE_DEFAULT = Path(__file__).resolve().parents[2] / "credentials" / "telegram-allowFrom.json"

# Known exclusions (bot/internal chats to never ingest)
# These are blocked even if somehow in allowlist
EXCLUDED_PATTERNS = {
    "responder",
    "mbresponder",
    "mresponder",
    "botfather",
}


class AllowlistConfigError(RuntimeError):
    """Configuration error for allowlist (missing/invalid)."""

    def __init__(self, message: str, reason_code: str = "telegram_not_configured"):
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


class ChatNotAllowedError(RuntimeError):
    """Chat is not in allowlist."""

    def __init__(self, chat_id: int, chat_title: Optional[str] = None):
        title = chat_title or "N/A"
        super().__init__(f"telegram_chat_not_allowed: chat_id={chat_id} title='{title}'")
        self.reason_code = "telegram_chat_not_allowed"
        self.chat_id = chat_id
        self.chat_title = chat_title


def _parse_ids(values: List[str], source_label: str) -> Tuple[Set[int], List[str]]:
    allowed: Set[int] = set()
    invalid: List[str] = []
    for part in values:
        text = str(part).strip()
        if not text:
            continue
        try:
            allowed.add(int(text))
        except ValueError:
            invalid.append(text)
    if invalid:
        logger.error(f"Invalid chat_id(s) in {source_label}: {invalid}")
    return allowed, invalid


def _load_allowlist_from_file(path: Path) -> Tuple[Set[int], List[str], str, List[str]]:
    if not path.exists():
        return set(), [], "missing", []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AllowlistConfigError(f"Allowlist file invalid JSON: {path} ({exc})")
    warnings: List[str] = []
    if "allow_chat_ids" in data:
        values = data.get("allow_chat_ids", [])
        if not isinstance(values, list):
            raise AllowlistConfigError(f"allow_chat_ids must be a list in {path}")
        allowed, invalid = _parse_ids(values, "allow_chat_ids")
        return allowed, invalid, "allow_chat_ids", warnings
    if "allowFrom" in data:
        values = data.get("allowFrom", [])
        if not isinstance(values, list):
            raise AllowlistConfigError(f"allowFrom must be a list in {path}")
        warnings.append(
            "Legacy allowFrom detected in credentials/telegram-allowFrom.json. "
            "Please migrate to allow_chat_ids."
        )
        allowed, invalid = _parse_ids(values, "allowFrom")
        return allowed, invalid, "allowFrom", warnings
    return set(), [], "missing", warnings


def resolve_allowlist() -> Tuple[Set[int], str, List[str], List[str]]:
    """
    Resolve the allowlist with precedence:
    1) ALLOWED_CHAT_IDS env var (if set)
    2) credentials/telegram-allowFrom.json
    3) ALLOWED_CHAT_IDS_DEFAULT (fallback)

    Returns:
        (allowlist_set, source_label, invalid_entries)
    """
    env_value = os.environ.get("ALLOWED_CHAT_IDS", "").strip()
    if env_value:
        parts = [p.strip() for p in env_value.split(",") if p.strip()]
        allowed, invalid = _parse_ids(parts, "ALLOWED_CHAT_IDS")
        return allowed, "env", invalid, []

    path = Path(os.environ.get("OPENCLAW_ALLOWLIST_PATH", str(ALLOWLIST_FILE_DEFAULT)))
    allowed, invalid, source_key, warnings = _load_allowlist_from_file(path)
    if allowed or invalid or path.exists():
        return allowed, f"credentials:{source_key}", invalid, warnings

    return ALLOWED_CHAT_IDS_DEFAULT.copy(), "default", [], []


def load_allowlist_from_env() -> Set[int]:
    """
    Load allowed chat IDs from ALLOWED_CHAT_IDS environment variable,
    falling back to credentials/telegram-allowFrom.json.

    Returns:
        Set of allowed chat IDs as integers.
        Falls back to ALLOWED_CHAT_IDS_DEFAULT if no config found.
    """
    allowed, source, invalid, warnings = resolve_allowlist()
    for warning in warnings:
        logger.warning(warning)
    if invalid:
        raise AllowlistConfigError(
            f"Invalid chat_id entries in allowlist ({source}): {invalid}"
        )
    if not allowed:
        logger.warning(
            "No allowed chat IDs configured (env and credentials empty). "
            "Allowlist is empty."
        )
    return allowed


def require_allowlist() -> Set[int]:
    """Load allowlist and fail fast if missing/invalid."""
    allowed, source, invalid, warnings = resolve_allowlist()
    for warning in warnings:
        logger.warning(warning)
    if invalid:
        raise AllowlistConfigError(
            f"Invalid chat_id entries in allowlist ({source}): {invalid}"
        )
    if not allowed:
        raise AllowlistConfigError(
            "No allowed Telegram chat IDs configured. "
            "Set ALLOWED_CHAT_IDS or add allow_chat_ids to credentials/telegram-allowFrom.json."
        )
    return allowed


def assert_chat_allowed(
    chat_id: int,
    chat_title: Optional[str] = None,
    allowlist: Optional[Set[int]] = None
) -> None:
    """Assert a chat is allowed, raising a structured error otherwise."""
    if allowlist is None:
        allowlist = require_allowlist()
    if chat_id not in allowlist:
        raise ChatNotAllowedError(chat_id, chat_title)


def is_chat_allowed(
    chat_id: int,
    chat_title: Optional[str] = None,
    allowlist: Optional[Set[int]] = None,
    raise_on_fail: bool = False
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
    if not allowlist:
        if raise_on_fail:
            raise AllowlistConfigError(
                "No allowed Telegram chat IDs configured. "
                "Set ALLOWED_CHAT_IDS or edit credentials/telegram-allowFrom.json."
            )
        logger.warning("Allowlist empty; dropping all chats.")
        return False

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
        if raise_on_fail:
            raise ChatNotAllowedError(chat_id, chat_title)
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
    allowlist, source, invalid, warnings = resolve_allowlist()

    logger.info("=" * 60)
    logger.info("ITC Pipeline - Allowlist Configuration")
    logger.info("=" * 60)
    logger.info(f"Allowlist source: {source}")
    logger.info(f"Allowed chat IDs: {len(allowlist)} entries")

    for chat_id in sorted(allowlist):
        logger.info(f"  - {chat_id}")

    if invalid:
        logger.error(f"Invalid allowlist entries: {invalid}")
    for warning in warnings:
        logger.warning(warning)

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
