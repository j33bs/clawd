from __future__ import annotations

from typing import Any, Dict, List, Optional

_DEFAULTS = {
    "method": "weighted_mean",
    "tie_break": "flat",
    "eps": 1e-9,
}


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        f = float(val)
    except Exception:
        return default
    if f != f:
        return default
    return f


def blend_signals(items: List[Dict[str, Any]], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    if not items:
        return {
            "signal": 0.0,
            "confidence": 0.0,
            "explanation": {"reason": "empty", "method": cfg["method"], "n": 0},
        }

    total_weight = 0.0
    total_effective = 0.0
    weighted_signal = 0.0
    weighted_conf = 0.0

    for it in items:
        if not isinstance(it, dict):
            continue
        signal = _to_float(it.get("signal"), 0.0)
        weight = _to_float(it.get("weight"), 1.0)
        confidence = _to_float(it.get("confidence"), 1.0)

        if weight < 0:
            weight = 0.0
        if confidence < 0:
            confidence = 0.0

        total_weight += weight
        effective = weight * confidence
        total_effective += effective
        weighted_signal += signal * effective
        weighted_conf += weight * confidence

    if total_effective <= 0:
        return {
            "signal": 0.0,
            "confidence": 0.0,
            "explanation": {"reason": "no_weight", "method": cfg["method"], "n": len(items)},
        }

    signal_value = weighted_signal / total_effective
    confidence = weighted_conf / total_weight if total_weight > 0 else 0.0

    tie_applied = False
    if abs(signal_value) < float(cfg.get("eps", 1e-9)):
        tie_break = cfg.get("tie_break", "flat")
        if tie_break == "bull":
            signal_value = 1.0
            tie_applied = True
        elif tie_break == "bear":
            signal_value = -1.0
            tie_applied = True
        else:
            signal_value = 0.0
            tie_applied = True

    return {
        "signal": signal_value,
        "confidence": max(0.0, min(1.0, confidence)),
        "explanation": {
            "method": cfg["method"],
            "n": len(items),
            "total_weight": total_weight,
            "total_effective": total_effective,
            "tie_applied": tie_applied,
        },
    }
