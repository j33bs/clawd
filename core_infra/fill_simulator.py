from __future__ import annotations


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _impact_bps(notional_usd: float, impact_bps_per_10k: float) -> float:
    notional = max(0.0, _safe_float(notional_usd))
    return (notional / 10000.0) * max(0.0, _safe_float(impact_bps_per_10k))


def market_fill_price(
    *,
    side: str,
    reference_price: float,
    best_bid: float | None = None,
    best_ask: float | None = None,
    slippage_bps: float = 0.0,
    spread_bps: float = 0.0,
    impact_bps_per_10k: float = 0.0,
    notional_usd: float = 0.0,
) -> dict:
    ref = max(0.0, _safe_float(reference_price))
    bid = _safe_float(best_bid, ref)
    ask = _safe_float(best_ask, ref)
    side_norm = str(side).lower()
    base_price = ask if side_norm == "buy" and ask > 0 else (bid if side_norm == "sell" and bid > 0 else ref)
    impact_bps = _impact_bps(notional_usd, impact_bps_per_10k)
    total_bps = max(0.0, _safe_float(slippage_bps)) + max(0.0, impact_bps)
    if base_price <= 0:
        base_price = ref
    if side_norm == "buy":
        if base_price <= 0 and ref > 0:
            base_price = ref * (1.0 + (max(0.0, _safe_float(spread_bps)) / 20000.0))
        fill_price = base_price * (1.0 + (total_bps / 10000.0))
    else:
        if base_price <= 0 and ref > 0:
            base_price = ref * (1.0 - (max(0.0, _safe_float(spread_bps)) / 20000.0))
        fill_price = base_price * (1.0 - (total_bps / 10000.0))
    return {
        "price": fill_price,
        "impact_bps": impact_bps,
        "slippage_bps": max(0.0, _safe_float(slippage_bps)),
        "spread_bps": max(0.0, _safe_float(spread_bps)),
        "role": "taker",
    }


def limit_fill_price(
    *,
    side: str,
    limit_price: float,
    trade_price: float,
    queue_buffer_bps: float = 0.0,
) -> dict | None:
    side_norm = str(side).lower()
    limit_px = max(0.0, _safe_float(limit_price))
    trade_px = max(0.0, _safe_float(trade_price))
    if limit_px <= 0 or trade_px <= 0:
        return None
    buffer_mult = 1.0 + (max(0.0, _safe_float(queue_buffer_bps)) / 10000.0)
    if side_norm == "buy":
        touched = trade_px <= (limit_px * buffer_mult)
    else:
        touched = trade_px >= (limit_px / max(1e-9, buffer_mult))
    if not touched:
        return None
    return {
        "price": limit_px,
        "impact_bps": 0.0,
        "slippage_bps": 0.0,
        "spread_bps": 0.0,
        "role": "maker",
    }


def estimate_liquidation_price(entry_price: float, direction: int, leverage: float, maintenance_margin_pct: float = 0.005) -> float | None:
    entry = max(0.0, _safe_float(entry_price))
    lev = max(1.0, _safe_float(leverage, 1.0))
    mm = max(0.0, _safe_float(maintenance_margin_pct))
    if entry <= 0:
        return None
    if int(direction) >= 0:
        floor_mult = max(0.01, 1.0 - (1.0 / lev) + mm)
        return entry * floor_mult
    ceil_mult = 1.0 + (1.0 / lev) - mm
    return entry * max(1.0001, ceil_mult)
