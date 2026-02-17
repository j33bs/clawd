from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class KnowledgeUnit:
    kind: str
    source: str
    agent_scope: str
    ttl_days: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_record(self, *, content: str, content_hash: str, created_at: Optional[datetime] = None) -> Dict[str, Any]:
        ts = created_at or _utc_now()
        expires_at = None
        if self.ttl_days is not None:
            expires_at = (ts + timedelta(days=int(self.ttl_days))).isoformat()
        return {
            "kind": self.kind,
            "source": self.source,
            "agent_scope": self.agent_scope,
            "ttl_days": self.ttl_days,
            "created_at": ts.isoformat(),
            "expires_at": expires_at,
            "content_hash": content_hash,
            "content": content,
            "metadata": self.metadata or {},
        }
