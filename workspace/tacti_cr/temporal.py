"""Temporal episodic memory with deterministic time-decay retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import exp
import json
from pathlib import Path
from typing import Dict, List, Optional

from .config import DEFAULT_CONFIG
from .hivemind_bridge import hivemind_query, hivemind_store
from .temporal_watchdog import temporal_reset_event


@dataclass
class TemporalEntry:
    timestamp: datetime
    content: str
    importance: float = 0.5
    decay_rate: float = DEFAULT_CONFIG.temporal.default_decay_rate
    metadata: Dict[str, str] = field(default_factory=dict)


class TemporalMemory:
    def __init__(
        self,
        retention_days: int = DEFAULT_CONFIG.temporal.retention_days,
        *,
        agent_scope: str = "main",
        sync_hivemind: bool = True,
    ):
        self._entries: List[TemporalEntry] = []
        self._retention_days = retention_days
        self._agent_scope = agent_scope
        self._sync_hivemind = sync_hivemind

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
        if self._sync_hivemind:
            hivemind_store(
                {
                    "kind": str((metadata or {}).get("kind", "fact")),
                    "source": "tacti_cr.temporal",
                    "agent_scope": str((metadata or {}).get("agent_scope", self._agent_scope)),
                    "content": content,
                    "ttl_days": None,
                }
            )
        drift = temporal_reset_event(content, now=entry.timestamp)
        if drift:
            path = Path(__file__).resolve().parents[2] / "workspace" / "state" / "temporal" / "watchdog_events.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(drift, ensure_ascii=True) + "\n")
        return entry

    def retrieve(
        self,
        query: str,
        limit: int = 5,
        now: Optional[datetime] = None,
        *,
        include_hivemind: bool = False,
        hivemind_limit: int = 3,
    ) -> List[TemporalEntry]:
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
        local_results = [entry for _, entry in scored[:limit]]

        if not include_hivemind:
            return local_results

        extra: List[TemporalEntry] = []
        seen = {e.content for e in local_results}
        for row in hivemind_query(query, agent=self._agent_scope, limit=hivemind_limit):
            text = row.content.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ts = now
            try:
                if row.created_at:
                    ts = datetime.fromisoformat(row.created_at)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                ts = now
            extra.append(
                TemporalEntry(
                    timestamp=ts,
                    content=text,
                    importance=max(0.1, min(1.0, row.score / 10.0)),
                    decay_rate=DEFAULT_CONFIG.temporal.default_decay_rate,
                    metadata={"source": row.source, "kind": row.kind, "agent_scope": row.agent_scope},
                )
            )

        merged = local_results + extra
        return merged[: max(1, int(limit))]

    def prune_expired(self, now: Optional[datetime] = None, max_age_days: Optional[int] = None) -> int:
        now = now or datetime.now(timezone.utc)
        age_limit = timedelta(days=max_age_days if max_age_days is not None else self._retention_days)
        before = len(self._entries)
        self._entries = [e for e in self._entries if (now - e.timestamp) <= age_limit]
        return before - len(self._entries)

    @property
    def size(self) -> int:
        return len(self._entries)
