from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from ._common import memory_ext_enabled, runtime_dir, utc_now_iso
except ImportError:  # pragma: no cover
    from _common import memory_ext_enabled, runtime_dir, utc_now_iso

def _arousal_state_path():
    return runtime_dir("memory_ext", "arousal_state.json")


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def compute_arousal(token_count: int, latency_ms: int, novelty_score: float, sentiment: float) -> float:
    tokens_term = float(max(0, token_count)) / 800.0
    latency_term = 1.0 / float(max(1, latency_ms))
    novelty_term = max(-1.0, min(1.0, float(novelty_score)))
    sentiment_term = max(-1.0, min(1.0, float(sentiment)))
    weighted = (0.9 * tokens_term) + (300.0 * latency_term) + (0.7 * novelty_term) + (0.4 * sentiment_term) - 1.2
    return max(0.0, min(1.0, _sigmoid(weighted)))


def arousal_to_state(arousal: float) -> str:
    level = max(0.0, min(1.0, float(arousal)))
    if level < 0.3:
        return "IDLE"
    if level < 0.6:
        return "ACTIVE"
    if level < 0.8:
        return "ENGAGED"
    return "OVERLOAD"


def modulate_response(arousal: float, base_response: str) -> str:
    state = arousal_to_state(arousal)
    text = str(base_response or "")
    if state == "OVERLOAD":
        clipped = text[:180].strip()
        if len(text) > 180:
            clipped += " ..."
        return "[CAUTION] " + clipped
    if state == "ENGAGED":
        return text[:260] if len(text) > 260 else text
    return text


def get_arousal_state(
    token_count: int = 0,
    latency_ms: int = 1000,
    novelty_score: float = 0.0,
    sentiment: float = 0.0,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    arousal = compute_arousal(token_count, latency_ms, novelty_score, sentiment)
    state = arousal_to_state(arousal)
    payload: Dict[str, Any] = {
        "timestamp_utc": utc_now_iso(now),
        "arousal": arousal,
        "state": state,
        "recommendation": "slow_down" if state == "OVERLOAD" else "proceed",
    }
    if memory_ext_enabled():
        state_path = _arousal_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


__all__ = ["compute_arousal", "arousal_to_state", "modulate_response", "get_arousal_state"]
