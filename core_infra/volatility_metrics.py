from __future__ import annotations

from math import log, isnan
from statistics import pstdev
from typing import Any, Dict, List, Optional

_DEFAULTS = {
    "atr_period": 14,
    "vol_period": 20,
    "min_price": 1e-12,
}


def _to_float(val) -> Optional[float]:
    try:
        f = float(val)
    except Exception:
        return None
    if isnan(f):
        return None
    return f


def _valid_close(val: float) -> bool:
    return val is not None and val > 0


def _valid_hlc(h: float, l: float, c: float) -> bool:
    return h is not None and l is not None and c is not None and h > 0 and l > 0 and c > 0


def compute_volatility(candles: List[Dict[str, Any]], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    atr_period = max(1, int(cfg["atr_period"]))
    vol_period = max(1, int(cfg["vol_period"]))

    closes: List[float] = []
    tr_values: List[float] = []

    prev_close: Optional[float] = None
    for c in candles:
        close = _to_float(c.get("c"))
        if _valid_close(close):
            closes.append(close)

        high = _to_float(c.get("h"))
        low = _to_float(c.get("l"))
        if not _valid_hlc(high, low, close):
            continue

        if high < low:
            high, low = low, high

        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
        prev_close = close

    atr = None
    atr_pct = None
    if len(tr_values) >= atr_period:
        window = tr_values[-atr_period:]
        atr = sum(window) / len(window)
        if closes:
            last_close = closes[-1]
            denom = max(abs(last_close), float(cfg["min_price"]))
            atr_pct = atr / denom

    rolling_vol = None
    rolling_vol_pct = None
    returns: List[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            returns.append(log(closes[i] / closes[i - 1]))
    if len(returns) >= vol_period:
        window = returns[-vol_period:]
        rolling_vol = pstdev(window)
        rolling_vol_pct = rolling_vol * 100.0

    window_used = min(vol_period, len(returns)) if returns else 0

    return {
        "atr": atr,
        "atr_pct": atr_pct,
        "rolling_vol": rolling_vol,
        "rolling_vol_pct": rolling_vol_pct,
        "n": len(closes),
        "window_used": window_used,
        "period_used": atr_period,
    }
