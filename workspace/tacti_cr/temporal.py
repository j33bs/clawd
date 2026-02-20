"""Temporal episodic memory with deterministic time-decay retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import exp
import json
import os
import hashlib
import math
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
        self._surprise_ema: float | None = None

    def store(
        self,
        content: str,
        *,
        importance: float = 0.5,
        decay_rate: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> TemporalEntry:
        gated_metadata = dict(metadata or {})
        if _surprise_gate_enabled():
            centroid = gated_metadata.get("reservoir_centroid")
            threshold = gated_metadata.get("surprise_threshold")
            floor = float(gated_metadata.get("surprise_floor", 0.05) or 0.05)
            mult = float(gated_metadata.get("surprise_mult", 1.2) or 1.2)
            ema_alpha = float(gated_metadata.get("surprise_ema_alpha", 0.2) or 0.2)
            surprise_score = None
            effective_threshold = float(threshold) if threshold is not None else floor
            if isinstance(centroid, list):
                surprise_score = surprise_score_proxy(content, centroid)
                if threshold is None:
                    baseline = self._surprise_ema if self._surprise_ema is not None else surprise_score
                    effective_threshold = max(floor, float(baseline) * mult)
                self._surprise_ema = (
                    surprise_score
                    if self._surprise_ema is None
                    else ((1.0 - ema_alpha) * self._surprise_ema) + (ema_alpha * surprise_score)
                )
            if isinstance(centroid, list) and surprise_score is not None and surprise_score < effective_threshold:
                return TemporalEntry(
                    timestamp=timestamp or datetime.now(timezone.utc),
                    content=content,
                    importance=max(0.0, min(1.0, importance)),
                    decay_rate=decay_rate if decay_rate is not None else DEFAULT_CONFIG.temporal.default_decay_rate,
                    metadata={
                        **gated_metadata,
                        "surprise_blocked": "1",
                        "surprise_score": round(float(surprise_score), 6),
                        "surprise_threshold": round(float(effective_threshold), 6),
                    },
                )

        entry = TemporalEntry(
            timestamp=timestamp or datetime.now(timezone.utc),
            content=content,
            importance=max(0.0, min(1.0, importance)),
            decay_rate=decay_rate if decay_rate is not None else DEFAULT_CONFIG.temporal.default_decay_rate,
            metadata=gated_metadata,
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


def _surprise_gate_enabled() -> bool:
    value = str(
        os.environ.get(
            "OPENCLAW_TEMPORAL_SURPRISE_GATE",
            os.environ.get("OPENCLAW_SURPRISE_GATE", "0"),
        )
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _embed_text(text: str, dim: int = 24) -> List[float]:
    vec = [0.0 for _ in range(dim)]
    for token in str(text or "").lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        vec[idx] += sign
    return vec


def text_embedding_proxy(content: str, dim: int = 24) -> List[float]:
    return _embed_text(content, dim=dim)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


def surprise_score_proxy(content: str, reservoir_centroid: List[float]) -> float:
    if not isinstance(reservoir_centroid, list) or not reservoir_centroid:
        return 1.0
    emb = _embed_text(content, dim=len(reservoir_centroid))
    p = _normalize_distribution(emb)
    q = _normalize_distribution([float(x) for x in reservoir_centroid])
    return _kl_divergence(p, q)


def should_write_episode(content: str, reservoir_centroid: List[float], threshold: float = 0.35) -> bool:
    return surprise_score_proxy(content, reservoir_centroid) >= float(threshold)


def _normalize_distribution(values: List[float], eps: float = 1e-9) -> List[float]:
    if not values:
        return [1.0]
    raw = [abs(float(v)) + eps for v in values]
    total = sum(raw)
    if total <= 0.0:
        return [1.0 / float(len(raw)) for _ in raw]
    return [v / total for v in raw]


def _kl_divergence(p: List[float], q: List[float], eps: float = 1e-9) -> float:
    size = min(len(p), len(q))
    if size <= 0:
        return 0.0
    value = 0.0
    for idx in range(size):
        pi = max(eps, float(p[idx]))
        qi = max(eps, float(q[idx]))
        value += pi * math.log(pi / qi)
    return max(0.0, float(value))
