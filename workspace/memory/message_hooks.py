from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .arousal_tracker import update_from_event as update_arousal
from .relationship_tracker import update_from_event as update_relationship


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def content_hash(text: str) -> str:
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_message_event(
    *,
    session_id: str,
    role: str,
    content: str,
    ts_utc: str | None = None,
    source: str = "teamchat",
    tone: str | None = None,
) -> dict[str, Any]:
    return {
        "ts_utc": str(ts_utc or _utc_now()),
        "type": "message_event",
        "session_id": str(session_id or "unknown"),
        "source": str(source or "unknown"),
        "role": str(role or "unknown"),
        "tone": str(tone or "unlabeled"),
        "content_hash": content_hash(content),
    }


def process_message_event(event: dict[str, Any], *, repo_root: Path | str) -> dict[str, Any]:
    root = Path(repo_root)
    arousal = update_arousal(event, repo_root=root)
    relationship = update_relationship(event, repo_root=root)
    return {"arousal": arousal, "relationship": relationship}


__all__ = ["build_message_event", "content_hash", "process_message_event"]
