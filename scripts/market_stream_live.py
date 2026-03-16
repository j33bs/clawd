#!/usr/bin/env python3
"""
Live market daemon for the trading sims.

Streams Binance public klines, aggTrade ticks, and best bid/ask updates for the
configured universe and keeps:
  - market/candles_15m.jsonl
  - market/candles_1h.jsonl
  - market/ticks.jsonl
  - market/tick_features.json

up to date for both the bar-driven and tick-informed model paths.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_infra.tick_microstructure import (
    DEFAULT_LOOKBACK_MS,
    append_jsonl,
    prune_trade_window,
    summarize_trade_window,
    write_tick_feature_snapshot,
)
from scripts import market_stream

DEFAULT_WS_BASE_URL = "wss://stream.binance.com:9443/stream"
DEFAULT_BYBIT_WS_BASE_URL = "wss://stream.bybit.com/v5/public/spot"
DEFAULT_KRAKEN_WS_BASE_URL = "wss://ws.kraken.com/v2"
DEFAULT_BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
LIVE_INTERVALS = ("15m", "1h")
TICKS_FILE = "ticks.jsonl"
TICK_FEATURES_FILE = "tick_features.json"
VENUE_QUOTES_FILE = "venue_quotes.jsonl"
CROSS_EXCHANGE_FEATURES_FILE = "cross_exchange_features.json"
FUNDING_HISTORY_FILE = "funding_rates.jsonl"
FUNDING_SNAPSHOT_FILE = "funding_snapshot.json"


def _build_stream_url(symbols, intervals=LIVE_INTERVALS, base_url: str = DEFAULT_WS_BASE_URL):
    streams = []
    for symbol in symbols:
        lower = str(symbol).lower()
        for interval in intervals:
            streams.append(f"{lower}@kline_{interval}")
        streams.append(f"{lower}@aggTrade")
        streams.append(f"{lower}@bookTicker")
    if not streams:
        raise ValueError("at least one symbol is required")
    return f"{base_url.rstrip('/')}?streams={'/'.join(streams)}"


def _split_symbols_by_provider(symbols):
    groups = {
        "legacy_crypto": [],
        "kraken_spot": [],
        "alpaca_equity": [],
    }
    for symbol in symbols:
        provider = market_stream.classify_symbol_provider(symbol)
        groups.setdefault(provider, []).append(str(symbol).upper() if provider != "kraken_spot" else str(symbol).upper())
    return groups


def _extract_kline_row(message):
    payload = message.get("data") if isinstance(message, dict) and "data" in message else message
    if not isinstance(payload, dict) or payload.get("e") != "kline":
        return None
    kline = payload.get("k") or {}
    interval = str(kline.get("i") or "")
    if interval not in market_stream.INTERVALS:
        return None
    symbol = str(payload.get("s") or "").upper()
    ts = kline.get("t")
    if not symbol or ts is None:
        return None
    return {
        "symbol": symbol,
        "ts": int(ts),
        "o": float(kline["o"]),
        "h": float(kline["h"]),
        "l": float(kline["l"]),
        "c": float(kline["c"]),
        "v": float(kline["v"]),
        "interval": interval,
        "source": "binance_ws",
        "closed": bool(kline.get("x", False)),
    }


def _extract_trade_row(message):
    payload = message.get("data") if isinstance(message, dict) and "data" in message else message
    if not isinstance(payload, dict) or payload.get("e") != "aggTrade":
        return None
    symbol = str(payload.get("s") or "").upper()
    ts = payload.get("T")
    if not symbol or ts is None:
        return None
    return {
        "type": "aggTrade",
        "symbol": symbol,
        "ts": int(ts),
        "price": float(payload.get("p", 0.0) or 0.0),
        "qty": float(payload.get("q", 0.0) or 0.0),
        "side": "sell" if bool(payload.get("m")) else "buy",
        "trade_id": int(payload.get("a", 0) or 0),
        "source": "binance_ws",
    }


def _extract_book_row(message):
    payload = message.get("data") if isinstance(message, dict) and "data" in message else message
    if not isinstance(payload, dict):
        return None
    event_name = str(payload.get("e") or "bookTicker")
    if event_name != "bookTicker":
        # Binance bookTicker combined stream payloads often omit `e`.
        if not {"s", "b", "a"}.issubset(set(payload.keys())):
            return None
    symbol = str(payload.get("s") or "").upper()
    if not symbol:
        return None
    return {
        "symbol": symbol,
        "ts": int(payload.get("E", 0) or payload.get("u", 0) or int(time.time() * 1000)),
        "best_bid": float(payload.get("b", 0.0) or 0.0),
        "best_ask": float(payload.get("a", 0.0) or 0.0),
    }


def _parse_iso_ms(raw):
    try:
        from datetime import datetime
        import re

        normalized = re.sub(r"\.(\d{6})\d+(?=[+-]\d{2}:\d{2}|Z$)", r".\1", str(raw))
        return int(datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def _extract_kraken_ticker_row(message):
    if not isinstance(message, dict) or str(message.get("channel") or "") != "ticker":
        return None
    rows = message.get("data") or []
    if not rows:
        return None
    row = rows[0]
    return {
        "symbol": str(row.get("symbol") or "").upper(),
        "ts": _parse_iso_ms(row.get("timestamp")),
        "best_bid": float(row.get("bid", 0.0) or 0.0),
        "best_ask": float(row.get("ask", 0.0) or 0.0),
    }


def _extract_kraken_trade_rows(message):
    if not isinstance(message, dict) or str(message.get("channel") or "") != "trade":
        return []
    rows = []
    for item in list(message.get("data") or []):
        symbol = str(item.get("symbol") or "").upper()
        if not symbol:
            continue
        rows.append(
            {
                "type": "trade",
                "symbol": symbol,
                "ts": _parse_iso_ms(item.get("timestamp")),
                "price": float(item.get("price", 0.0) or 0.0),
                "qty": float(item.get("qty", 0.0) or 0.0),
                "side": str(item.get("side") or "buy"),
                "trade_id": int(item.get("trade_id", 0) or 0),
                "source": "kraken_ws",
            }
        )
    return rows


def _extract_kraken_ohlc_rows(message):
    if not isinstance(message, dict) or str(message.get("channel") or "") != "ohlc":
        return []
    out = []
    for item in list(message.get("data") or []):
        symbol = str(item.get("symbol") or "").upper()
        interval = int(item.get("interval", 0) or 0)
        interval_name = {15: "15m", 60: "1h"}.get(interval)
        ts = _parse_iso_ms(item.get("interval_begin"))
        if not symbol or not interval_name:
            continue
        out.append(
            {
                "symbol": symbol,
                "ts": ts,
                "o": float(item.get("open", 0.0) or 0.0),
                "h": float(item.get("high", 0.0) or 0.0),
                "l": float(item.get("low", 0.0) or 0.0),
                "c": float(item.get("close", 0.0) or 0.0),
                "v": float(item.get("volume", 0.0) or 0.0),
                "interval": interval_name,
                "source": "kraken_ws",
                "closed": False,
            }
        )
    return out


def _build_bybit_subscribe_payload(symbols):
    args = [f"orderbook.1.{str(symbol).upper()}" for symbol in symbols]
    return {"op": "subscribe", "args": args}


def _build_kraken_subscribe_payload(channel, symbols, **extra):
    return {
        "method": "subscribe",
        "params": {
            "channel": channel,
            "symbol": list(symbols),
            **extra,
        },
    }


def _extract_bybit_orderbook_row(message):
    if not isinstance(message, dict):
        return None
    topic = str(message.get("topic") or "")
    if not topic.startswith("orderbook.1."):
        return None
    symbol = topic.split(".")[-1].upper()
    payload = message.get("data") or {}
    bids = payload.get("b") or []
    asks = payload.get("a") or []
    if not bids or not asks:
        return None
    try:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
    except Exception:
        return None
    return {
        "symbol": symbol,
        "ts": int(message.get("ts", 0) or payload.get("u", 0) or int(time.time() * 1000)),
        "best_bid": best_bid,
        "best_ask": best_ask,
    }


def _quote_row(symbol, venue, ts, best_bid, best_ask):
    bid = float(best_bid or 0.0)
    ask = float(best_ask or 0.0)
    mid = None
    spread_bps = None
    if bid > 0 and ask > 0 and ask >= bid:
        mid = (bid + ask) / 2.0
        if mid > 0:
            spread_bps = ((ask - bid) / mid) * 10000.0
    return {
        "symbol": str(symbol).upper(),
        "venue": str(venue),
        "ts": int(ts),
        "best_bid": bid,
        "best_ask": ask,
        "mid_price": mid,
        "spread_bps": spread_bps,
    }


def _update_venue_quote_state(venue_state, *, venue, row, market_dir: Path):
    symbol_state = venue_state.setdefault(row["symbol"], {})
    quote = _quote_row(row["symbol"], venue, row["ts"], row["best_bid"], row["best_ask"])
    existing = symbol_state.get(venue)
    if existing == quote:
        return False
    symbol_state[venue] = quote
    append_jsonl(market_dir / VENUE_QUOTES_FILE, quote)
    return True


def _write_cross_exchange_snapshot(market_dir: Path, venue_state):
    symbols = {}
    generated_at = 0
    for symbol, venues in venue_state.items():
        binance = venues.get("binance_spot")
        bybit = venues.get("bybit_spot")
        kraken = venues.get("kraken_spot")
        if not binance and not bybit and not kraken:
            continue
        generated_at = max(
            generated_at,
            int((binance or {}).get("ts", 0) or 0),
            int((bybit or {}).get("ts", 0) or 0),
            int((kraken or {}).get("ts", 0) or 0),
        )
        row = {
            "binance_spot": binance,
            "bybit_spot": bybit,
            "kraken_spot": kraken,
        }
        if binance and bybit:
            binance_mid = binance.get("mid_price")
            bybit_mid = bybit.get("mid_price")
            if isinstance(binance_mid, (int, float)) and isinstance(bybit_mid, (int, float)) and float(binance_mid) > 0:
                gap_bps = ((float(bybit_mid) / float(binance_mid)) - 1.0) * 10000.0
                row["mid_gap_bps"] = gap_bps
                if gap_bps > 0:
                    row["buy_venue"] = "binance_spot"
                    row["sell_venue"] = "bybit_spot"
                else:
                    row["buy_venue"] = "bybit_spot"
                    row["sell_venue"] = "binance_spot"
        symbols[symbol] = row
    payload = {"version": 1, "generated_at": generated_at, "symbols": symbols}
    (market_dir / CROSS_EXCHANGE_FEATURES_FILE).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fetch_json(url: str):
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_funding_row(symbol: str, funding_url: str = DEFAULT_BINANCE_FUNDING_URL):
    payload = _fetch_json(f"{funding_url}?symbol={str(symbol).upper()}")
    if not isinstance(payload, dict):
        return None
    mark_price = payload.get("markPrice")
    index_price = payload.get("indexPrice")
    funding_rate = payload.get("lastFundingRate")
    next_ts = payload.get("nextFundingTime")
    if mark_price is None or funding_rate is None:
        return None
    return {
        "symbol": str(symbol).upper(),
        "ts": int(payload.get("time", 0) or int(time.time() * 1000)),
        "mark_price": float(mark_price),
        "index_price": float(index_price) if index_price is not None else None,
        "last_funding_rate": float(funding_rate),
        "next_funding_time": int(next_ts) if next_ts is not None else None,
        "source": "binance_futures_rest",
    }


def _load_state(market_dir: Path, interval: str):
    target = market_dir / market_stream.INTERVALS[interval]["file"]
    state = {}
    for row in market_stream.load_jsonl(target):
        symbol = row.get("symbol")
        ts = row.get("ts")
        if symbol is None or ts is None:
            continue
        state[(str(symbol), int(ts))] = row
    return state


def _apply_row(state_by_interval, row):
    interval = row["interval"]
    state = state_by_interval.setdefault(interval, {})
    key = (row["symbol"], int(row["ts"]))
    existing = state.get(key)
    if existing == row:
        return False
    state[key] = row
    return True


def _flush_state(market_dir: Path, state_by_interval):
    for interval, state in state_by_interval.items():
        target = market_dir / market_stream.INTERVALS[interval]["file"]
        rows = sorted(state.values(), key=lambda item: (item["symbol"], int(item["ts"])))
        market_stream.write_jsonl(target, rows)


def _refresh_tick_features(
    *,
    market_dir: Path,
    tick_state: dict[str, list[dict]],
    book_state: dict[str, dict],
    lookback_ms: int,
) -> dict[str, dict]:
    features_by_symbol = {}
    for symbol, trades in tick_state.items():
        latest = book_state.get(symbol) or {}
        features_by_symbol[symbol] = summarize_trade_window(
            symbol,
            trades,
            best_bid=latest.get("best_bid"),
            best_ask=latest.get("best_ask"),
            lookback_ms=lookback_ms,
        )
    write_tick_feature_snapshot(market_dir / TICK_FEATURES_FILE, features_by_symbol)
    return features_by_symbol


async def _poll_binance_funding(
    *,
    symbols,
    market_dir: Path,
    funding_url: str,
    poll_interval_sec: float,
):
    snapshot = {"version": 1, "generated_at": 0, "symbols": {}}
    while True:
        try:
            rows = []
            for symbol in symbols:
                row = await asyncio.to_thread(_fetch_funding_row, symbol, funding_url)
                if row is None:
                    continue
                rows.append(row)
                append_jsonl(market_dir / FUNDING_HISTORY_FILE, row)
            if rows:
                snapshot = {
                    "version": 1,
                    "generated_at": max(int(row["ts"]) for row in rows),
                    "symbols": {row["symbol"]: row for row in rows},
                }
                (market_dir / FUNDING_SNAPSHOT_FILE).write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        except asyncio.CancelledError:
            raise
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            print(f"market_funding_reconnect reason={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
        await asyncio.sleep(float(poll_interval_sec))


async def _run_bybit_quotes(
    *,
    symbols,
    market_dir: Path,
    venue_state,
    reconnect_sec: float,
    ws_base_url: str,
):
    import websockets

    payload = _build_bybit_subscribe_payload(symbols)
    while True:
        try:
            async with websockets.connect(ws_base_url, ping_interval=20, ping_timeout=20, max_size=2**20) as conn:
                await conn.send(json.dumps(payload))
                print("market_bybit_connected", flush=True)
                while True:
                    raw = await conn.recv()
                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    row = _extract_bybit_orderbook_row(message)
                    if row is None:
                        continue
                    if _update_venue_quote_state(venue_state, venue="bybit_spot", row=row, market_dir=market_dir):
                        _write_cross_exchange_snapshot(market_dir, venue_state)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"market_bybit_reconnect reason={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
            await asyncio.sleep(float(reconnect_sec))


async def _run_kraken_stream(
    *,
    symbols,
    market_dir: Path,
    state_by_interval,
    tick_state,
    book_state,
    venue_state,
    tick_lookback_ms: int,
    flush_interval_sec: float,
    reconnect_sec: float,
    ws_base_url: str,
):
    import websockets

    payloads = [
        _build_kraken_subscribe_payload("ticker", symbols),
        _build_kraken_subscribe_payload("trade", symbols),
        _build_kraken_subscribe_payload("ohlc", symbols, interval=15),
        _build_kraken_subscribe_payload("ohlc", symbols, interval=60),
    ]
    while True:
        last_flush = time.monotonic()
        try:
            async with websockets.connect(ws_base_url, ping_interval=20, ping_timeout=20, max_size=2**20) as conn:
                for payload in payloads:
                    await conn.send(json.dumps(payload))
                print("market_kraken_connected", flush=True)
                while True:
                    raw = await conn.recv()
                    try:
                        message = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    changed = False
                    flush_reason = None
                    kline_rows = _extract_kraken_ohlc_rows(message)
                    for row in kline_rows:
                        changed = _apply_row(state_by_interval, row) or changed
                        flush_reason = f"kline:{row['interval']}"
                    trade_rows = _extract_kraken_trade_rows(message)
                    last_trade = None
                    for trade in trade_rows:
                        append_jsonl(market_dir / TICKS_FILE, trade)
                        window = tick_state[trade["symbol"]]
                        window.append(trade)
                        prune_trade_window(window, now_ts=trade["ts"], lookback_ms=tick_lookback_ms)
                        changed = True
                        flush_reason = flush_reason or "tick"
                        last_trade = trade
                    book = _extract_kraken_ticker_row(message)
                    if book is not None:
                        book_state[book["symbol"]] = book
                        _update_venue_quote_state(venue_state, venue="kraken_spot", row=book, market_dir=market_dir)
                        _write_cross_exchange_snapshot(market_dir, venue_state)
                        changed = True
                        flush_reason = flush_reason or "book"
                    if not changed:
                        continue
                    now = time.monotonic()
                    if flush_reason == "tick":
                        _refresh_tick_features(
                            market_dir=market_dir,
                            tick_state=tick_state,
                            book_state=book_state,
                            lookback_ms=tick_lookback_ms,
                        )
                    if flush_reason and (str(flush_reason).startswith("kline:") or (now - last_flush) >= float(flush_interval_sec)):
                        _flush_state(market_dir, state_by_interval)
                        features_by_symbol = _refresh_tick_features(
                            market_dir=market_dir,
                            tick_state=tick_state,
                            book_state=book_state,
                            lookback_ms=tick_lookback_ms,
                        )
                        _write_cross_exchange_snapshot(market_dir, venue_state)
                        last_flush = now
                        if kline_rows:
                            row = kline_rows[-1]
                            print(
                                f"market_kraken_update interval={row['interval']} symbol={row['symbol']} ts={row['ts']}",
                                flush=True,
                            )
                        elif last_trade is not None:
                            latest = features_by_symbol.get(last_trade["symbol"], {})
                            print(
                                f"market_kraken_tick symbol={last_trade['symbol']} ts={last_trade['ts']} "
                                f"trades={latest.get('trade_count', 0)} imbalance={latest.get('imbalance', 0.0):+.3f}",
                                flush=True,
                            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"market_kraken_reconnect reason={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
            await asyncio.sleep(float(reconnect_sec))


async def _poll_equity_bars(
    *,
    symbols,
    market_dir: Path,
    state_by_interval,
    poll_interval_sec: float,
    limit: int = 16,
):
    if not symbols:
        return
    while True:
        try:
            changed = False
            fetched_rows = 0
            for interval in LIVE_INTERVALS:
                for symbol in symbols:
                    try:
                        rows = market_stream.fetch_public_klines(symbol, interval, limit)
                    except RuntimeError as exc:
                        print(
                            f"market_equity_poll_skip symbol={symbol} interval={interval} reason={exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                        continue
                    for row in rows[-8:]:
                        fetched_rows += 1
                        changed = _apply_row(state_by_interval, dict(row, closed=False)) or changed
            if changed:
                _flush_state(market_dir, state_by_interval)
                print(
                    f"market_equity_poll_update symbols={','.join(symbols)} rows={fetched_rows}",
                    flush=True,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"market_equity_poll_error reason={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
        await asyncio.sleep(float(poll_interval_sec))


async def run_live(
    *,
    config_path: Path,
    symbols=None,
    market_dir: Path = market_stream.MARKET_DIR,
    backfill_limit: int = 300,
    tick_lookback_ms: int = DEFAULT_LOOKBACK_MS,
    flush_interval_sec: float = 2.0,
    reconnect_sec: float = 5.0,
    ws_base_url: str = DEFAULT_WS_BASE_URL,
    bybit_ws_base_url: str = DEFAULT_BYBIT_WS_BASE_URL,
    kraken_ws_base_url: str = DEFAULT_KRAKEN_WS_BASE_URL,
    funding_url: str = DEFAULT_BINANCE_FUNDING_URL,
    funding_poll_sec: float = 30.0,
    equity_poll_sec: float = 60.0,
):
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("websockets package is required: python3 -m pip install --user --break-system-packages websockets") from exc

    resolved_symbols = market_stream.resolve_symbols(config_path, cli_symbols=symbols)
    if not resolved_symbols:
        raise RuntimeError(f"no symbols resolved from {config_path}")
    provider_groups = _split_symbols_by_provider(resolved_symbols)
    legacy_symbols = provider_groups.get("legacy_crypto", [])
    kraken_symbols = provider_groups.get("kraken_spot", [])
    alpaca_symbols = provider_groups.get("alpaca_equity", [])

    if backfill_limit > 0:
        market_stream.run(
            config_path=config_path,
            symbols=resolved_symbols,
            limit=backfill_limit,
            full=False,
            market_dir=market_dir,
        )

    state_by_interval = {interval: _load_state(market_dir, interval) for interval in LIVE_INTERVALS}
    tick_state = defaultdict(list)
    book_state = {}
    venue_state = defaultdict(dict)
    url = _build_stream_url(legacy_symbols, base_url=ws_base_url) if legacy_symbols else None
    print(
        "market_live_start "
        f"legacy={','.join(legacy_symbols) or '-'} "
        f"kraken={','.join(kraken_symbols) or '-'} "
        f"alpaca={','.join(alpaca_symbols) or '-'}",
        flush=True,
    )
    if alpaca_symbols:
        if all(market_stream._alpaca_credentials()):
            print(f"market_equity_source provider=alpaca symbols={','.join(alpaca_symbols)}", flush=True)
        else:
            fallback_provider = market_stream.resolve_public_equity_provider()
            if fallback_provider:
                print(
                    f"market_equity_source provider={fallback_provider}_fallback symbols={','.join(alpaca_symbols)}",
                    flush=True,
                )
            else:
                print(
                    f"market_alpaca_skipped reason=credentials_missing symbols={','.join(alpaca_symbols)}",
                    file=sys.stderr,
                    flush=True,
                )

    async def _run_binance_stream():
        if not legacy_symbols or not url:
            return
        last_flush = time.monotonic()
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=2**20) as conn:
                    print("market_live_connected", flush=True)
                    while True:
                        raw = await conn.recv()
                        try:
                            message = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        row = _extract_kline_row(message)
                        trade = _extract_trade_row(message)
                        book = _extract_book_row(message)
                        changed = False
                        flush_reason = None
                        if row is not None:
                            changed = _apply_row(state_by_interval, row) or changed
                            if row.get("closed"):
                                flush_reason = f"kline:{row['interval']}"
                        if trade is not None:
                            append_jsonl(market_dir / TICKS_FILE, trade)
                            window = tick_state[trade["symbol"]]
                            window.append(trade)
                            prune_trade_window(window, now_ts=trade["ts"], lookback_ms=tick_lookback_ms)
                            changed = True
                            flush_reason = flush_reason or "tick"
                        if book is not None:
                            book_state[book["symbol"]] = book
                            _update_venue_quote_state(venue_state, venue="binance_spot", row=book, market_dir=market_dir)
                            _write_cross_exchange_snapshot(market_dir, venue_state)
                            changed = True
                            flush_reason = flush_reason or "book"
                        if not changed:
                            continue
                        now = time.monotonic()
                        if flush_reason == "tick":
                            tick_ts = trade["ts"]
                            _refresh_tick_features(
                                market_dir=market_dir,
                                tick_state=tick_state,
                                book_state=book_state,
                                lookback_ms=tick_lookback_ms,
                            )
                        if flush_reason and (flush_reason.startswith("kline:") or (now - last_flush) >= float(flush_interval_sec)):
                            _flush_state(market_dir, state_by_interval)
                            features_by_symbol = _refresh_tick_features(
                                market_dir=market_dir,
                                tick_state=tick_state,
                                book_state=book_state,
                                lookback_ms=tick_lookback_ms,
                            )
                            _write_cross_exchange_snapshot(market_dir, venue_state)
                            last_flush = now
                            if row is not None and row.get("closed"):
                                print(
                                    f"market_live_update interval={row['interval']} symbol={row['symbol']} "
                                    f"ts={row['ts']} closed={str(bool(row.get('closed'))).lower()}",
                                    flush=True,
                                )
                            elif trade is not None:
                                latest = features_by_symbol.get(trade["symbol"], {})
                                print(
                                    f"market_tick_update symbol={trade['symbol']} ts={tick_ts} "
                                    f"trades={latest.get('trade_count', 0)} imbalance={latest.get('imbalance', 0.0):+.3f}",
                                    flush=True,
                                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"market_live_reconnect reason={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
                await asyncio.sleep(float(reconnect_sec))

    tasks = [
        asyncio.create_task(_run_binance_stream()),
    ]
    if legacy_symbols:
        tasks.append(
            asyncio.create_task(
                _run_bybit_quotes(
                    symbols=legacy_symbols,
                    market_dir=market_dir,
                    venue_state=venue_state,
                    reconnect_sec=reconnect_sec,
                    ws_base_url=bybit_ws_base_url,
                )
            )
        )
        tasks.append(
            asyncio.create_task(
                _poll_binance_funding(
                    symbols=legacy_symbols,
                    market_dir=market_dir,
                    funding_url=funding_url,
                    poll_interval_sec=funding_poll_sec,
                )
            )
        )
    if kraken_symbols:
        tasks.append(
            asyncio.create_task(
                _run_kraken_stream(
                    symbols=kraken_symbols,
                    market_dir=market_dir,
                    state_by_interval=state_by_interval,
                    tick_state=tick_state,
                    book_state=book_state,
                    venue_state=venue_state,
                    tick_lookback_ms=tick_lookback_ms,
                    flush_interval_sec=flush_interval_sec,
                    reconnect_sec=reconnect_sec,
                    ws_base_url=kraken_ws_base_url,
                )
            )
        )
    if alpaca_symbols:
        tasks.append(
            asyncio.create_task(
                _poll_equity_bars(
                    symbols=alpaca_symbols,
                    market_dir=market_dir,
                    state_by_interval=state_by_interval,
                    poll_interval_sec=equity_poll_sec,
                )
            )
        )
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        _flush_state(market_dir, state_by_interval)
        _refresh_tick_features(market_dir=market_dir, tick_state=tick_state, book_state=book_state, lookback_ms=tick_lookback_ms)
        _write_cross_exchange_snapshot(market_dir, venue_state)
        raise
    except KeyboardInterrupt:
        for task in tasks:
            task.cancel()
        _flush_state(market_dir, state_by_interval)
        _refresh_tick_features(market_dir=market_dir, tick_state=tick_state, book_state=book_state, lookback_ms=tick_lookback_ms)
        _write_cross_exchange_snapshot(market_dir, venue_state)
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stream live market data into the local candle/tick files")
    parser.add_argument("--config", type=str, default=None, help="Override trading config path")
    parser.add_argument("--symbol", action="append", default=None, help="Override config symbols (repeatable)")
    parser.add_argument("--market-dir", type=str, default=None, help="Override market directory")
    parser.add_argument("--backfill-limit", type=int, default=300, help="Initial REST backfill per symbol/timeframe")
    parser.add_argument("--tick-lookback-ms", type=int, default=DEFAULT_LOOKBACK_MS, help="Rolling tick lookback window")
    parser.add_argument("--flush-interval-sec", type=float, default=2.0, help="How often to flush open candle updates")
    parser.add_argument("--reconnect-sec", type=float, default=5.0, help="Reconnect wait after websocket failure")
    parser.add_argument("--ws-base-url", type=str, default=DEFAULT_WS_BASE_URL, help="Override Binance websocket base URL")
    parser.add_argument("--bybit-ws-base-url", type=str, default=DEFAULT_BYBIT_WS_BASE_URL, help="Override Bybit websocket base URL")
    parser.add_argument("--kraken-ws-base-url", type=str, default=DEFAULT_KRAKEN_WS_BASE_URL, help="Override Kraken websocket base URL")
    parser.add_argument("--funding-url", type=str, default=DEFAULT_BINANCE_FUNDING_URL, help="Override Binance funding snapshot URL")
    parser.add_argument("--funding-poll-sec", type=float, default=30.0, help="Polling interval for Binance funding snapshots")
    args = parser.parse_args(argv)

    config_path = market_stream.resolve_path(args.config, market_stream.CONFIG_ENV, market_stream.DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        print(f"ERROR: config not found at {config_path}", file=sys.stderr)
        return 2

    market_dir = Path(args.market_dir) if args.market_dir else market_stream.MARKET_DIR

    try:
        return asyncio.run(
            run_live(
                config_path=config_path,
                symbols=args.symbol,
                market_dir=market_dir,
                backfill_limit=args.backfill_limit,
                tick_lookback_ms=args.tick_lookback_ms,
                flush_interval_sec=args.flush_interval_sec,
                reconnect_sec=args.reconnect_sec,
                ws_base_url=args.ws_base_url,
                bybit_ws_base_url=args.bybit_ws_base_url,
                kraken_ws_base_url=args.kraken_ws_base_url,
                funding_url=args.funding_url,
                funding_poll_sec=args.funding_poll_sec,
            )
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
