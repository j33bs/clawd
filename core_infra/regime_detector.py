from __future__ import annotations
from dataclasses import dataclass
from math import isnan
from typing import Any, Dict, List, Optional

_DEFAULTS = {
    "lookback": 96,
    "sideways_threshold": 0.002,   # 0.2% move over lookback -> sideways
    "conf_scale": 0.01,            # 1% move -> ~1.0 pre-trend factor
    "min_price": 1e-12,
}


def _clean_prices(prices: List[float]) -> List[float]:
    out: List[float] = []
    for p in prices:
        try:
            fp = float(p)
        except Exception:
            continue
        if fp <= 0 or isnan(fp):
            continue
        out.append(fp)
    return out


def detect_regime(prices: List[float], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    p = _clean_prices(prices)
    if len(p) < 3:
        return {
            "regime": "sideways",
            "confidence": 0.0,
            "features": {"reason": "insufficient_data", "n": len(p)},
        }

    lb = int(cfg["lookback"])
    if lb <= 2:
        lb = 3
    window = p[-lb:] if len(p) >= lb else p

    first = window[0]
    last = window[-1]
    denom = max(abs(first), float(cfg["min_price"]))
    norm_slope = (last - first) / denom  # coarse normalized drift

    # trend strength proxy: fraction of returns with same sign as overall slope
    rets = [(window[i] / window[i-1] - 1.0) for i in range(1, len(window)) if window[i-1] > 0]
    if not rets:
        trend_strength = 0.0
    else:
        sign = 1 if norm_slope > 0 else (-1 if norm_slope < 0 else 0)
        aligned = sum(1 for r in rets if (r > 0 and sign > 0) or (r < 0 and sign < 0))
        trend_strength = aligned / len(rets)

    sideways_th = float(cfg["sideways_threshold"])
    if abs(norm_slope) < sideways_th:
        regime = "sideways"
    else:
        regime = "bull" if norm_slope > 0 else "bear"

    conf_scale = max(float(cfg["conf_scale"]), 1e-9)
    base_conf = min(1.0, abs(norm_slope) / conf_scale)
    confidence = max(0.0, min(1.0, base_conf * (0.5 + 0.5 * trend_strength)))

    return {
        "regime": regime,
        "confidence": confidence,
        "features": {
            "n": len(window),
            "lookback_used": len(window),
            "norm_slope": norm_slope,
            "trend_strength": trend_strength,
            "sideways_threshold": sideways_th,
            "conf_scale": conf_scale,
        },
    }
