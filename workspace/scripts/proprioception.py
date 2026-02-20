from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List


class ProprioceptiveSampler:
    """Rolling deterministic sampler for router-internal state."""

    def __init__(self, maxlen: int = 200):
        self._buffer: Deque[Dict[str, object]] = deque(maxlen=max(10, int(maxlen)))
        self._breaker_open_providers: List[str] = []

    def record_decision(
        self,
        duration_ms,
        tokens_in=None,
        tokens_out=None,
        provider=None,
        ok=True,
        err=None,
    ):
        self._buffer.append(
            {
                "duration_ms": float(duration_ms),
                "tokens_in": int(tokens_in) if isinstance(tokens_in, int) else None,
                "tokens_out": int(tokens_out) if isinstance(tokens_out, int) else None,
                "provider": str(provider) if provider is not None else None,
                "ok": bool(ok),
                "err": str(err) if err else None,
            }
        )

    def set_breaker_open_providers(self, providers):
        unique = sorted({str(p) for p in (providers or []) if str(p).strip()})
        self._breaker_open_providers = unique

    def _quantile(self, values: List[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(float(v) for v in values)
        if len(ordered) == 1:
            return ordered[0]
        pos = max(0.0, min(1.0, float(q))) * (len(ordered) - 1)
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        frac = pos - lo
        return ordered[lo] + ((ordered[hi] - ordered[lo]) * frac)

    def snapshot(self):
        durations = [float(item.get("duration_ms", 0.0) or 0.0) for item in self._buffer]
        errors = sum(1 for item in self._buffer if not item.get("ok", False))
        count = len(self._buffer)
        return {
            "latency_ms_p50": round(self._quantile(durations, 0.50), 6),
            "latency_ms_p95": round(self._quantile(durations, 0.95), 6),
            "decisions_last_n": count,
            "error_rate": round((errors / float(count)) if count else 0.0, 6),
            "breaker_open_providers": list(self._breaker_open_providers),
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }


__all__ = ["ProprioceptiveSampler"]
