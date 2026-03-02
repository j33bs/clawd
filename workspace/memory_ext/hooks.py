from __future__ import annotations

from typing import Any, Dict, Optional

from .arousal_detector import compute_arousal, get_arousal_state
from .ipnb_practices import mwe_activator, somatic_checkin


def pre_response_hook(text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ctx = dict(context or {})
    token_count = int(ctx.get("token_count") or len(str(text or "").split()))
    latency_ms = int(ctx.get("latency_ms") or 1000)
    novelty = float(ctx.get("novelty_score") or 0.0)
    sentiment = float(ctx.get("sentiment") or 0.0)

    somatic = somatic_checkin()
    arousal = compute_arousal(token_count, latency_ms, novelty, sentiment)
    arousal_state = get_arousal_state(token_count, latency_ms, novelty, sentiment)

    return {
        "somatic": somatic,
        "arousal": arousal,
        "arousal_state": arousal_state,
    }


def relationship_hook(text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ = context or {}
    cue_result = mwe_activator(text)
    if cue_result.get("mode") == "co_regulated":
        return {"relationship": cue_result, "activated": True}
    return {"relationship": cue_result, "activated": False}


__all__ = ["pre_response_hook", "relationship_hook"]
