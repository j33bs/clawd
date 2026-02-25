from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from ._common import memory_ext_enabled, runtime_dir, utc_now_iso
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir, utc_now_iso


def _phi_log_path() -> Path:
    return runtime_dir("memory_ext", "phi_metrics.md")


def _token_set(text: str) -> Set[str]:
    return {tok for tok in str(text or "").lower().split() if tok}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return float(len(a & b)) / float(len(union))


def measure_coherence(sections: List[str]) -> float:
    if len(sections) < 2:
        return 1.0 if sections else 0.0
    pairs = []
    for idx in range(len(sections) - 1):
        pairs.append(_jaccard(_token_set(sections[idx]), _token_set(sections[idx + 1])))
    return max(0.0, min(1.0, sum(pairs) / float(len(pairs))))


def measure_integration(sections: List[str]) -> float:
    if not sections:
        return 0.0
    mid = max(1, len(sections) // 2)
    left = _token_set(" ".join(sections[:mid]))
    right = _token_set(" ".join(sections[mid:]))
    return max(0.0, min(1.0, _jaccard(left, right)))


def phi_score(sections: List[str]) -> Dict[str, Any]:
    coherence = measure_coherence(sections)
    integration = measure_integration(sections)
    novelty = max(0.0, min(1.0, 1.0 - coherence))
    phi = max(0.0, min(1.0, (coherence + integration + (1.0 - novelty)) / 3.0))
    return {
        "phi": phi,
        "components": {
            "coherence": coherence,
            "integration": integration,
            "novelty_proxy": novelty,
        },
    }


def log_phi(session_id: str, score: Dict[str, Any], now: Optional[datetime] = None) -> None:
    if not memory_ext_enabled():
        return
    phi_log = _phi_log_path()
    phi_log.parent.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso(now)
    line = "- {ts} session_id={sid} phi={phi:.6f}".format(ts=ts, sid=session_id, phi=float(score.get("phi", 0.0)))
    with phi_log.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


__all__ = ["measure_coherence", "measure_integration", "phi_score", "log_phi"]
