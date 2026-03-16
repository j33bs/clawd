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
import hashlib
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, asdict

from .allowlist import is_chat_allowed, log_allowlist_on_startup
from core_infra.channel_scoring import load_channel_scores
from core_infra.strategy_blender import blend_signals
from workspace.itc.ingest.interfaces import RawPayload, emit_event, persist_artifacts, validate_signal
try:
    from workspace.memory.message_hooks import build_message_event, process_message_event
except Exception:  # pragma: no cover
    build_message_event = None
    process_message_event = None

logger = logging.getLogger(__name__)

# Dedupe state file location
DEDUPE_STATE_PATH = Path(os.environ.get(
    "ITC_DEDUPE_STATE_PATH",
    str(Path(__file__).parent.parent.parent / "telegram" / "itc_processed_messages.json")
))

# Maximum dedupe entries to keep (rolling window)
DEDUPE_MAX_ENTRIES = 10000
_ITC_CLASSIFIER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "itc_classify.py"
_ITC_CANON_PATH = Path(__file__).resolve().parents[2] / "itc" / "canon" / "messages.jsonl"
_ITC_ARTIFACT_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "itc"
_ITC_CHANNEL_SCORES_PATH = Path(__file__).resolve().parents[2] / "itc" / "channel_scores.json"
_CLASSIFY_RULES = None

_BULLISH_PATTERNS = (
    re.compile(r"\b(long|buy|bull(?:ish)?|accumulat(?:e|ion)|breakout|upside)\b", re.I),
)
_BEARISH_PATTERNS = (
    re.compile(r"\b(short|sell|bear(?:ish)?|distribution|breakdown|downside)\b", re.I),
)
_STRUCTURED_SIGNAL_HINTS = (
    re.compile(r"\b(entry|target|tp|sl|stop(?:\s|-)loss|invalidat(?:e|ion)|leverage)\b", re.I),
    re.compile(r"[$€£]?\d[\d,]*(?:\.\d+)?"),
)


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
    if not is_chat_allowed(message.chat_id, message.chat_title, raise_on_fail=True):
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
    if callable(build_message_event) and callable(process_message_event):
        try:
            event = build_message_event(
                session_id=f"{message.source}:{message.chat_id}",
                role="user",
                content=message.text,
                ts_utc=message.date,
                source=message.source,
                tone="unlabeled",
            )
            process_message_event(event, repo_root=Path(__file__).resolve().parents[2])
        except Exception:
            pass

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
    # Preserve existing queue contract.
    output_path = DEDUPE_STATE_PATH.parent / "itc_incoming_queue.jsonl"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "a") as f:
            f.write(json.dumps(message.to_dict()) + "\n")
        logger.debug(f"Queued message to {output_path}")
    except Exception as e:
        logger.error(f"Failed to queue message: {e}")

    # Also forward to classifier input contract consumed by scripts/itc_classify.py.
    classify = _resolve_classifier()
    primary_tag = "noise"
    all_tags = ["noise"]
    if callable(classify):
        try:
            primary, tags = classify(message.text or "")
            if isinstance(primary, str) and primary:
                primary_tag = primary
            if isinstance(tags, list) and tags:
                all_tags = [str(tag) for tag in tags if str(tag).strip()]
        except Exception as e:
            logger.warning(f"ITC classifier bridge failed; using fallback tag: {e}")
    try:
        _ITC_CANON_PATH.parent.mkdir(parents=True, exist_ok=True)
        canonical_row = {
            "hash": hashlib.sha256(f"{message.dedupe_key()}:{message.text}".encode("utf-8")).hexdigest(),
            "source": message.source,
            "chat_id": message.chat_id,
            "message_id": message.message_id,
            "date": message.date,
            "text": message.text,
            "primary_tag": primary_tag,
            "all_tags": all_tags,
            "classifier": "ingestion_boundary.forwarder/rules",
        }
        with _ITC_CANON_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(canonical_row, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed classifier forward write: {e}")
    try:
        _persist_contract_signal(message, primary_tag, all_tags)
    except Exception as e:
        logger.error(f"Failed ITC contract signal write: {e}")


def _resolve_classifier():
    global _CLASSIFY_RULES
    if _CLASSIFY_RULES is not None:
        return _CLASSIFY_RULES
    if not _ITC_CLASSIFIER_PATH.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("itc_classify_bridge", str(_ITC_CLASSIFIER_PATH))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, "classify_rules", None)
        if callable(fn):
            _CLASSIFY_RULES = fn
            return _CLASSIFY_RULES
    except Exception as e:
        logger.warning(f"Classifier module load failed: {e}")
    return None


def _normalize_ts_utc(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if text.endswith("Z"):
        return text
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _channel_key(chat_title: Optional[str]) -> str:
    title = str(chat_title or "").lower()
    if "cryptocosm" in title:
        return "cryptocosm"
    if "cryptoverse" in title or "itc" in title:
        return "cryptoverse"
    return "telegram"


def _infer_message_signal(primary_tag: str, text: str) -> Optional[float]:
    body = str(text or "")
    if not body or primary_tag == "spam":
        return None
    bullish = any(pattern.search(body) for pattern in _BULLISH_PATTERNS)
    bearish = any(pattern.search(body) for pattern in _BEARISH_PATTERNS)
    structured = any(pattern.search(body) for pattern in _STRUCTURED_SIGNAL_HINTS)

    if bullish and not bearish:
        return 1.0 if primary_tag == "trade_signal" else 0.35
    if bearish and not bullish:
        return -1.0 if primary_tag == "trade_signal" else -0.35
    if primary_tag == "trade_signal" and structured:
        return 0.25
    if primary_tag == "news":
        return 0.0
    return None


def _infer_message_confidence(primary_tag: str, text: str, channel_weight: float) -> float:
    structured_hits = sum(1 for pattern in _STRUCTURED_SIGNAL_HINTS if pattern.search(str(text or "")))
    if primary_tag == "trade_signal":
        base = 0.58 + min(0.22, structured_hits * 0.11)
    elif primary_tag == "news":
        base = 0.42 + min(0.18, structured_hits * 0.09)
    else:
        base = 0.0
    scaled = base * max(0.25, min(1.5, float(channel_weight or 1.0)))
    return max(0.0, min(1.0, scaled))


def _build_contract_signal(message: IngestedMessage, primary_tag: str, all_tags: list[str]) -> Optional[dict[str, Any]]:
    del all_tags
    signal_value = _infer_message_signal(primary_tag, message.text)
    if signal_value is None:
        return None
    channel_weight = float(load_channel_scores(str(_ITC_CHANNEL_SCORES_PATH)).get(_channel_key(message.chat_title), 1.0))
    blended = blend_signals(
        [
            {
                "source": _channel_key(message.chat_title),
                "signal": signal_value,
                "weight": channel_weight,
                "confidence": _infer_message_confidence(primary_tag, message.text, channel_weight),
            }
        ]
    )
    sentiment = max(-1.0, min(1.0, float(blended.get("signal", 0.0) or 0.0)))
    confidence = max(0.0, min(1.0, float(blended.get("confidence", 0.0) or 0.0)))
    risk_on = max(0.0, min(1.0, (sentiment + 1.0) / 2.0))
    signal = {
        "schema_version": 1,
        "source": "telegram",
        "ts_utc": _normalize_ts_utc(message.date),
        "window": "1h",
        "metrics": {
            "risk_on": risk_on,
            "risk_off": 1.0 - risk_on,
            "sentiment": sentiment,
            "regime": "risk_on" if sentiment >= 0.0 else "risk_off",
            "confidence": confidence,
        },
        "raw_ref": "pending://telegram_message",
        "signature": f"sha256:{hashlib.sha256(message.text.encode('utf-8')).hexdigest()}",
    }
    ok, _ = validate_signal(signal)
    return signal if ok else None


def _persist_contract_signal(message: IngestedMessage, primary_tag: str, all_tags: list[str]) -> Optional[dict[str, str]]:
    signal = _build_contract_signal(message, primary_tag, all_tags)
    if signal is None:
        return None
    raw_payload = {
        "message": message.to_dict(),
        "primary_tag": primary_tag,
        "all_tags": all_tags,
        "channel_key": _channel_key(message.chat_title),
    }
    raw = RawPayload(
        content=json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        extension="json",
        metadata={"source": "telegram_ingestion_boundary"},
    )
    paths = persist_artifacts(raw, signal, run_id="telegram_ingestion_boundary", artifact_root=_ITC_ARTIFACT_ROOT)
    emit_event(
        "itc_telegram_signal_emitted",
        "telegram_ingestion_boundary",
        {
            "chat_id": message.chat_id,
            "message_id": message.message_id,
            "primary_tag": primary_tag,
            "signal_ts": signal["ts_utc"],
            "normalized_ref": paths["normalized_path"],
        },
        _ITC_ARTIFACT_ROOT,
    )
    return paths


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
