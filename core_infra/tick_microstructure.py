from __future__ import annotations

import json
import math
from pathlib import Path

DEFAULT_LOOKBACK_MS = 5 * 60 * 1000


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def prune_trade_window(trades: list[dict], *, now_ts: int, lookback_ms: int = DEFAULT_LOOKBACK_MS) -> None:
    cutoff = int(now_ts) - int(lookback_ms)
    while trades and int(trades[0].get("ts", 0) or 0) < cutoff:
        trades.pop(0)


def summarize_trade_window(
    symbol: str,
    trades: list[dict],
    *,
    best_bid: float | None = None,
    best_ask: float | None = None,
    lookback_ms: int = DEFAULT_LOOKBACK_MS,
) -> dict:
    if not trades:
        return {
            "symbol": symbol,
            "asof_ts": 0,
            "window_ms": int(lookback_ms),
            "trade_count": 0,
            "last_price": None,
            "volume": 0.0,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "imbalance": 0.0,
            "window_return": 0.0,
            "momentum_1m": 0.0,
            "realized_vol": 0.0,
            "avg_trade_size": 0.0,
            "trades_per_sec": 0.0,
            "vwap": None,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": None,
            "spread_bps": None,
        }

    ordered = sorted(trades, key=lambda row: int(row.get("ts", 0) or 0))
    first = ordered[0]
    last = ordered[-1]
    prices = [float(row.get("price", 0.0) or 0.0) for row in ordered]
    qtys = [float(row.get("qty", 0.0) or 0.0) for row in ordered]
    count = len(ordered)
    volume = sum(qtys)
    buy_volume = 0.0
    sell_volume = 0.0
    for row in ordered:
        qty = float(row.get("qty", 0.0) or 0.0)
        if str(row.get("side", "")).lower() == "buy":
            buy_volume += qty
        else:
            sell_volume += qty

    imbalance = (buy_volume - sell_volume) / volume if volume > 0 else 0.0
    first_price = float(first.get("price", 0.0) or 0.0)
    last_price = float(last.get("price", 0.0) or 0.0)
    window_return = ((last_price / first_price) - 1.0) if first_price > 0 and last_price > 0 else 0.0

    minute_anchor_price = first_price
    minute_cutoff = int(last.get("ts", 0) or 0) - 60_000
    for row in ordered:
        row_ts = int(row.get("ts", 0) or 0)
        row_price = float(row.get("price", 0.0) or 0.0)
        if row_ts >= minute_cutoff and row_price > 0:
            minute_anchor_price = row_price
            break
    momentum_1m = ((last_price / minute_anchor_price) - 1.0) if minute_anchor_price > 0 and last_price > 0 else window_return

    log_returns = []
    for prev, cur in zip(prices, prices[1:]):
        if prev > 0 and cur > 0:
            log_returns.append(math.log(cur / prev))
    realized_vol = math.sqrt(sum(x * x for x in log_returns) / len(log_returns)) if log_returns else 0.0

    duration_ms = max(1, int(last.get("ts", 0) or 0) - int(first.get("ts", 0) or 0))
    trades_per_sec = count / max(1.0, duration_ms / 1000.0)
    avg_trade_size = volume / count if count else 0.0
    vwap = (sum(price * qty for price, qty in zip(prices, qtys)) / volume) if volume > 0 else None

    mid_price = None
    spread_bps = None
    if best_bid is not None and best_ask is not None and best_bid > 0 and best_ask > 0 and best_ask >= best_bid:
        mid_price = (float(best_bid) + float(best_ask)) / 2.0
        if mid_price > 0:
            spread_bps = ((float(best_ask) - float(best_bid)) / mid_price) * 10000.0

    return {
        "symbol": symbol,
        "asof_ts": int(last.get("ts", 0) or 0),
        "window_ms": int(lookback_ms),
        "trade_count": count,
        "last_price": last_price,
        "volume": volume,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "imbalance": _clip(imbalance),
        "window_return": window_return,
        "momentum_1m": momentum_1m,
        "realized_vol": realized_vol,
        "avg_trade_size": avg_trade_size,
        "trades_per_sec": trades_per_sec,
        "vwap": vwap,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "spread_bps": spread_bps,
    }


def write_tick_feature_snapshot(path: Path, features_by_symbol: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": max([0] + [int((row or {}).get("asof_ts", 0) or 0) for row in features_by_symbol.values()]),
        "symbols": features_by_symbol,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_tick_feature_snapshot(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    symbols = payload.get("symbols", {})
    return symbols if isinstance(symbols, dict) else {}
