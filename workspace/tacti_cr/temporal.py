"""Temporal episodic memory with deterministic time-decay retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import exp
from typing import Dict, List, Optional

from .config import DEFAULT_CONFIG


@dataclass
class TemporalEntry:
    timestamp: datetime
    content: str
    importance: float = 0.5
    decay_rate: float = DEFAULT_CONFIG.temporal.default_decay_rate
    metadata: Dict[str, str] = field(default_factory=dict)


class TemporalMemory:
    def __init__(self, retention_days: int = DEFAULT_CONFIG.temporal.retention_days):
        self._entries: List[TemporalEntry] = []
        self._retention_days = retention_days

    def store(
        self,
        content: str,
        *,
        importance: float = 0.5,
        decay_rate: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> TemporalEntry:
        entry = TemporalEntry(
            timestamp=timestamp or datetime.now(timezone.utc),
            content=content,
            importance=max(0.0, min(1.0, importance)),
            decay_rate=decay_rate if decay_rate is not None else DEFAULT_CONFIG.temporal.default_decay_rate,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        return entry

    def retrieve(self, query: str, limit: int = 5, now: Optional[datetime] = None) -> List[TemporalEntry]:
        now = now or datetime.now(timezone.utc)
        query_terms = set((query or "").lower().split())

        scored = []
        for entry in self._entries:
            age_days = max(0.0, (now - entry.timestamp).total_seconds() / 86400.0)
            decay = exp(-entry.decay_rate * age_days)
            content_terms = set(entry.content.lower().split())
            overlap = len(query_terms & content_terms)
            relevance = 0.2 + (overlap * 0.1)
            score = entry.importance * decay * relevance
            scored.append((score, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def prune_expired(self, now: Optional[datetime] = None, max_age_days: Optional[int] = None) -> int:
        now = now or datetime.now(timezone.utc)
        age_limit = timedelta(days=max_age_days if max_age_days is not None else self._retention_days)
        before = len(self._entries)
        self._entries = [e for e in self._entries if (now - e.timestamp) <= age_limit]
        return before - len(self._entries)

    @property
    def size(self) -> int:
        return len(self._entries)
