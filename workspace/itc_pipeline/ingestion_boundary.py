#!/usr/bin/env python3
"""
ITC Pipeline - Ingestion Boundary
Category: C (Feature)

This is THE entry point where messages enter the ITC pipeline.
All ingestion must flow through this boundary.

Responsibilities:
1. Receive normalized messages from readers (Telegram, etc.)
2. Apply allowlist gate (HARD - drops non-allowed)
3. Dedupe by (source, chat_id, message_id)
4. Classify by tier (PRIMARY, OFFICIAL, COMMUNITY)
5. Forward to downstream processing

Message Schema (normalized):
{
    "source": "telegram",
    "chat_id": -1001234567890,
    "message_id": 12345,
    "date": "2026-02-05T12:00:00Z",
    "sender_id": 123456789,
    "sender_name": "User Name",
    "chat_title": "ITC Lifetime Lounge",
    "text": "Message content here",
    "raw_metadata": { ... }
}
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, asdict

from .allowlist import is_chat_allowed, log_allowlist_on_startup

logger = logging.getLogger(__name__)

# Dedupe state file location
DEDUPE_STATE_PATH = Path(os.environ.get(
    "ITC_DEDUPE_STATE_PATH",
    str(Path(__file__).parent.parent.parent / "telegram" / "itc_processed_messages.json")
))

# Maximum dedupe entries to keep (rolling window)
DEDUPE_MAX_ENTRIES = 10000


@dataclass
class IngestedMessage:
    """Normalized message structure for the ITC pipeline."""
    source: str
    chat_id: int
    message_id: int
    date: str  # ISO 8601
    sender_id: Optional[int]
    sender_name: Optional[str]
    chat_title: Optional[str]
    text: str
    raw_metadata: Dict[str, Any]

    # Set after classification
    classification: Optional[str] = None  # PRIMARY, OFFICIAL, COMMUNITY
    authority_weight: Optional[float] = None

    def dedupe_key(self) -> str:
        """Generate unique key for deduplication."""
        return f"{self.source}:{self.chat_id}:{self.message_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class DedupeStore:
    """
    Tracks processed message IDs to prevent duplicates.
    Uses a rolling window to bound memory/storage.
    """

    def __init__(self, state_path: Path = DEDUPE_STATE_PATH):
        self.state_path = state_path
        self._processed: Set[str] = set()
        self._load()

    def _load(self):
        """Load processed message IDs from state file."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    data = json.load(f)
                    self._processed = set(data.get("processed_keys", []))
                    logger.info(f"Loaded {len(self._processed)} dedupe entries from {self.state_path}")
            except Exception as e:
                logger.error(f"Failed to load dedupe state: {e}")
                self._processed = set()
        else:
            logger.info(f"No dedupe state file at {self.state_path}, starting fresh")

    def _save(self):
        """Persist processed message IDs to state file."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)

            # Trim to max entries (keep most recent)
            keys_list = list(self._processed)
            if len(keys_list) > DEDUPE_MAX_ENTRIES:
                keys_list = keys_list[-DEDUPE_MAX_ENTRIES:]
                self._processed = set(keys_list)

            with open(self.state_path, "w") as f:
                json.dump({
                    "version": 1,
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "count": len(keys_list),
                    "processed_keys": keys_list
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save dedupe state: {e}")

    def is_duplicate(self, key: str) -> bool:
        """Check if message has already been processed."""
        return key in self._processed

    def mark_processed(self, key: str):
        """Mark a message as processed."""
        self._processed.add(key)
        # Save periodically (every 100 new entries)
        if len(self._processed) % 100 == 0:
            self._save()

    def save(self):
        """Force save of dedupe state."""
        self._save()


# Global dedupe store instance
_dedupe_store: Optional[DedupeStore] = None


def get_dedupe_store() -> DedupeStore:
    """Get or create the global dedupe store."""
    global _dedupe_store
    if _dedupe_store is None:
        _dedupe_store = DedupeStore()
    return _dedupe_store


def ingest_message(
    message: IngestedMessage,
    dry_run: bool = False,
    dedupe_store: Optional[DedupeStore] = None
) -> bool:
    """
    INGESTION BOUNDARY - Main entry point for all messages.

    This function:
    1. Applies allowlist gate (drops non-allowed chats)
    2. Checks for duplicates
    3. Logs acceptance/rejection
    4. Forwards to downstream processing (unless dry_run)

    Args:
        message: Normalized message to ingest
        dry_run: If True, log what would happen but don't process
        dedupe_store: Optional dedupe store (uses global if not provided)

    Returns:
        True if message was accepted for processing, False if dropped
    """
    if dedupe_store is None:
        dedupe_store = get_dedupe_store()

    # === GATE 1: Allowlist ===
    if not is_chat_allowed(message.chat_id, message.chat_title):
        # Already logged in is_chat_allowed at DEBUG level
        return False

    # === GATE 2: Dedupe ===
    dedupe_key = message.dedupe_key()
    if dedupe_store.is_duplicate(dedupe_key):
        logger.debug(
            f"DEDUPE: Dropping duplicate message {dedupe_key}"
        )
        return False

    # === ACCEPTED ===
    logger.info(
        f"INGEST: source={message.source} chat_id={message.chat_id} "
        f"msg_id={message.message_id} chat='{message.chat_title}' "
        f"text_len={len(message.text)}"
    )

    if dry_run:
        logger.info(f"DRY-RUN: Would process message {dedupe_key}")
        return True

    # Mark as processed
    dedupe_store.mark_processed(dedupe_key)

    # TODO: Forward to classification/downstream processing
    # This will be wired to the ITC tier classification logic
    _forward_to_pipeline(message)

    return True


def _forward_to_pipeline(message: IngestedMessage):
    """
    Forward accepted message to downstream ITC pipeline processing.

    Currently logs the message; will be extended to:
    - Classify into PRIMARY/OFFICIAL/COMMUNITY tiers
    - Apply authority weights
    - Store in digest format
    """
    # For now, write to a processing queue file
    output_path = DEDUPE_STATE_PATH.parent / "itc_incoming_queue.jsonl"

    try:
        with open(output_path, "a") as f:
            f.write(json.dumps(message.to_dict()) + "\n")
        logger.debug(f"Queued message to {output_path}")
    except Exception as e:
        logger.error(f"Failed to queue message: {e}")


def initialize_ingestion():
    """
    Initialize the ingestion boundary.
    Call this on startup before processing messages.
    """
    log_allowlist_on_startup()
    get_dedupe_store()  # Initialize dedupe
    logger.info("Ingestion boundary initialized and ready")


if __name__ == "__main__":
    # Test the ingestion boundary
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    initialize_ingestion()
