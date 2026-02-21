"""Temporal episodic memory with deterministic time-decay retrieval."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import exp, log
from pathlib import Path
from typing import Dict, List, Optional

from .config import DEFAULT_CONFIG
from .events import emit
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
        self._surprise_ema: Optional[float] = None

    def store(
        self,
        content: str,
        *,
        importance: float = 0.5,
        decay_rate: Optional[float] = None,
        metadata: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> TemporalEntry:
        metadata = dict(metadata or {})
        entry = TemporalEntry(
            timestamp=timestamp or datetime.now(timezone.utc),
            content=content,
            importance=max(0.0, min(1.0, importance)),
            decay_rate=decay_rate if decay_rate is not None else DEFAULT_CONFIG.temporal.default_decay_rate,
            metadata=metadata,
        )
        if _surprise_gate_enabled():
            centroid = metadata.get("reservoir_centroid")
            if not isinstance(centroid, list):
                centroid = text_embedding_proxy(str(content))
            score = surprise_score_proxy(str(content), centroid)
            alpha = _coerce_float(metadata.get("surprise_ema_alpha"), 0.3)
            if self._surprise_ema is None:
                self._surprise_ema = float(score)
            else:
                self._surprise_ema = (float(alpha) * float(score)) + ((1.0 - float(alpha)) * float(self._surprise_ema))
            floor = _coerce_float(metadata.get("surprise_floor"), 0.01)
            mult = _coerce_float(metadata.get("surprise_mult"), 1.2)
            threshold = metadata.get("surprise_threshold")
            if threshold is None:
                threshold = max(floor, float(self._surprise_ema) * mult)
            threshold = float(threshold)
            entry.metadata["surprise_score"] = f"{float(score):.6f}"
            entry.metadata["surprise_threshold"] = f"{threshold:.6f}"
            if float(score) < threshold:
                entry.metadata["surprise_blocked"] = "1"
                return entry

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
            emit(
                "tacti_cr.temporal.drift_detected",
                {"agent_scope": self._agent_scope, "drift": drift},
                now=entry.timestamp,
            )
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


def _coerce_float(value, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _normalize_distribution(values: list[float], eps: float = 1e-12) -> list[float]:
    row = [max(eps, float(v)) for v in (values or [])]
    if not row:
        return [1.0]
    total = sum(row)
    if total <= eps:
        return [1.0 / float(len(row)) for _ in row]
    return [v / total for v in row]


def text_embedding_proxy(text: str, dim: int = 16) -> list[float]:
    tokens = [tok for tok in re.findall(r"[a-z0-9_]+", str(text or "").lower()) if tok]
    vec = [0.0] * max(4, int(dim))
    if not tokens:
        return _normalize_distribution([1.0] * len(vec))
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % len(vec)
        vec[idx] += 1.0
    return _normalize_distribution(vec)


def surprise_score_proxy(p, q, eps: float = 1e-12) -> float:
    p_vec = text_embedding_proxy(p) if isinstance(p, str) else _normalize_distribution([float(x) for x in (p or [])], eps=eps)
    q_vec = text_embedding_proxy(q) if isinstance(q, str) else _normalize_distribution([float(x) for x in (q or [])], eps=eps)
    if len(p_vec) != len(q_vec):
        size = max(len(p_vec), len(q_vec))
        p_vec = _normalize_distribution((p_vec + [eps] * size)[:size], eps=eps)
        q_vec = _normalize_distribution((q_vec + [eps] * size)[:size], eps=eps)
    score = 0.0
    for p_i, q_i in zip(p_vec, q_vec):
        score += p_i * log((p_i + eps) / (q_i + eps))
    return float(max(0.0, score))


def _surprise_gate_enabled() -> bool:
    from os import environ

    for key in ("OPENCLAW_TEMPORAL_SURPRISE_GATE", "OPENCLAW_SURPRISE_GATE"):
        if str(environ.get(key, "")).strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False
