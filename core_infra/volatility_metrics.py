from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple

_DEFAULTS = {
    "atr_period": 14,
    "vol_window": 30,
    "min_price": 1e-12,
}


def _get(c: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        if k in c and c[k] is not None:
            try:
                return float(c[k])
            except Exception:
                return None
    return None


def _extract_ohlc(candle: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    o = _get(candle, "open", "o")
    h = _get(candle, "high", "h")
    l = _get(candle, "low", "l")
    cl = _get(candle, "close", "c")
    if o is None or h is None or l is None or cl is None:
        return None
    if h <= 0 or l <= 0 or cl <= 0:
        return None
    return o, h, l, cl


def compute_atr(candles: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
    period = max(1, int(period))
    ohlc = [x for x in (_extract_ohlc(c) for c in candles) if x is not None]
    if len(ohlc) < period + 1:
        return {"atr": None, "atr_pct": None, "n": len(ohlc), "period_used": period}

    trs: List[float] = []
    prev_close = ohlc[0][3]
    for (_, high, low, close) in ohlc[1:]:
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close

    window = trs[-period:]
    atr = sum(window) / len(window)
    last_close = ohlc[-1][3]
    atr_pct = (atr / max(abs(last_close), _DEFAULTS["min_price"])) if last_close else None
    return {"atr": atr, "atr_pct": atr_pct, "n": len(ohlc), "period_used": period}


def compute_rolling_vol(prices: List[float], window: int = 30) -> Dict[str, Any]:
    window = max(2, int(window))
    p = [float(x) for x in prices if x is not None and float(x) > 0]
    if len(p) < window + 1:
        return {"rolling_vol": None, "rolling_vol_pct": None, "n": len(p), "window_used": window}

    # log returns
    rets: List[float] = []
    for i in range(1, len(p)):
        rets.append(math.log(p[i] / p[i - 1]))

    w = rets[-window:]
    mean = sum(w) / len(w)
    var = sum((r - mean) ** 2 for r in w) / len(w)
    vol = math.sqrt(var)
    return {"rolling_vol": vol, "rolling_vol_pct": vol * 100.0, "n": len(p), "window_used": window}


def compute_volatility(
    candles: Optional[List[Dict[str, Any]]] = None,
    prices: Optional[List[float]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    derived_prices: List[float] = []
    if prices:
        derived_prices = list(prices)
    elif candles:
        for c in candles:
            ohlc = _extract_ohlc(c)
            if ohlc is not None:
                derived_prices.append(ohlc[3])

    atr_out = compute_atr(candles or [], int(cfg["atr_period"])) if candles else {
        "atr": None,
        "atr_pct": None,
        "n": 0,
        "period_used": int(cfg["atr_period"]),
    }
    vol_out = compute_rolling_vol(derived_prices, int(cfg["vol_window"])) if derived_prices else {
        "rolling_vol": None,
        "rolling_vol_pct": None,
        "n": 0,
        "window_used": int(cfg["vol_window"]),
    }

    return {
        "atr": atr_out["atr"],
        "atr_pct": atr_out["atr_pct"],
        "rolling_vol": vol_out["rolling_vol"],
        "rolling_vol_pct": vol_out["rolling_vol_pct"],
        "n": max(int(atr_out.get("n", 0)), int(vol_out.get("n", 0))),
        "window_used": vol_out.get("window_used"),
        "period_used": atr_out.get("period_used"),
    }
