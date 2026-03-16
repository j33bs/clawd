#!/usr/bin/env python3
"""
Market candle fetcher for the trading sims.

Fetches public OHLCV candles for the configured trading universe and writes:
  - market/candles_15m.jsonl
  - market/candles_1h.jsonl

The output format matches what scripts/sim_runner.py already expects.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "pipelines" / "system1_trading.yaml"
CONFIG_ENV = "OPENCLAW_CONFIG_PATH"
DEFAULT_BINANCE_BASE_URL = "https://api.binance.com"
DEFAULT_BYBIT_BASE_URL = "https://api.bybit.com"
DEFAULT_KRAKEN_BASE_URL = "https://api.kraken.com/0/public"
DEFAULT_ALPACA_DATA_BASE_URL = "https://data.alpaca.markets/v2"
DEFAULT_YAHOO_CHART_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
MARKET_DIR = REPO_ROOT / "market"
INTERVALS = {
    "15m": {
        "file": "candles_15m.jsonl",
        "step_ms": 15 * 60 * 1000,
        "bybit_interval": "15",
        "kraken_interval": 15,
        "alpaca_timeframe": "15Min",
        "yahoo_interval": "15m",
        "yahoo_range": "60d",
    },
    "1h": {
        "file": "candles_1h.jsonl",
        "step_ms": 60 * 60 * 1000,
        "bybit_interval": "60",
        "kraken_interval": 60,
        "alpaca_timeframe": "1Hour",
        "yahoo_interval": "1h",
        "yahoo_range": "60d",
    },
}


def resolve_path(cli_value, env_var, default_path):
    if cli_value:
        return Path(cli_value)
    env_val = os.getenv(env_var)
    if env_val:
        return Path(env_val)
    return Path(default_path)


def load_config(config_path: Path):
    if yaml is None:
        raise RuntimeError("pyyaml is required; install with: python3 -m pip install pyyaml")
    with open(config_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_symbols(config_path: Path, cli_symbols=None):
    if cli_symbols:
        return sorted({str(symbol).upper() for symbol in cli_symbols if str(symbol).strip()})
    cfg = load_config(config_path)
    out = set()
    for sim in cfg.get("sims", []):
        for symbol in sim.get("universe", []):
            out.add(str(symbol).upper())
    return sorted(out)


def classify_symbol_provider(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if "/" in normalized:
        return "kraken_spot"
    if normalized.isalpha() and 1 <= len(normalized) <= 5:
        return "alpaca_equity"
    return "legacy_crypto"


def _alpaca_credentials() -> tuple[str | None, str | None]:
    key = (
        os.getenv("APCA_API_KEY_ID")
        or os.getenv("ALPACA_API_KEY")
        or os.getenv("OPENCLAW_ALPACA_API_KEY_ID")
    )
    secret = (
        os.getenv("APCA_API_SECRET_KEY")
        or os.getenv("ALPACA_API_SECRET")
        or os.getenv("OPENCLAW_ALPACA_API_SECRET_KEY")
    )
    return (key.strip() if key else None, secret.strip() if secret else None)


def resolve_public_equity_provider() -> str:
    raw = (os.getenv("OPENCLAW_PUBLIC_EQUITY_PROVIDER") or "yahoo").strip().lower()
    if raw in {"", "auto", "yahoo"}:
        return "yahoo"
    if raw in {"none", "off", "disabled"}:
        return ""
    return raw


def _http_get_json(url: str, timeout: int = 30, headers: dict[str, str] | None = None):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "clawd-market-stream/1.0",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _normalize_binance_klines(symbol: str, interval: str, rows):
    out = []
    for row in rows or []:
        if len(row) < 6:
            continue
        out.append(
            {
                "symbol": symbol,
                "ts": int(row[0]),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
                "interval": interval,
                "source": "binance",
            }
        )
    return out


def _normalize_bybit_klines(symbol: str, interval: str, rows):
    out = []
    for row in rows or []:
        if len(row) < 6:
            continue
        out.append(
            {
                "symbol": symbol,
                "ts": int(row[0]),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
                "interval": interval,
                "source": "bybit",
            }
        )
    out.sort(key=lambda item: (item["symbol"], item["ts"]))
    return out


def _normalize_kraken_ohlc(symbol: str, interval: str, rows):
    out = []
    for row in rows or []:
        if len(row) < 7:
            continue
        out.append(
            {
                "symbol": symbol,
                "ts": int(float(row[0]) * 1000),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[6]),
                "interval": interval,
                "source": "kraken",
            }
        )
    out.sort(key=lambda item: (item["symbol"], item["ts"]))
    return out


def _iso_to_ms(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        from datetime import datetime
        import re

        normalized = re.sub(r"\.(\d{6})\d+(?=[+-]\d{2}:\d{2}|Z$)", r".\1", raw)
        return int(datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def _normalize_alpaca_bars(symbol: str, interval: str, rows):
    out = []
    for row in rows or []:
        ts = _iso_to_ms(row.get("t"))
        if ts is None:
            continue
        out.append(
            {
                "symbol": symbol,
                "ts": ts,
                "o": float(row.get("o", 0.0) or 0.0),
                "h": float(row.get("h", 0.0) or 0.0),
                "l": float(row.get("l", 0.0) or 0.0),
                "c": float(row.get("c", 0.0) or 0.0),
                "v": float(row.get("v", 0.0) or 0.0),
                "interval": interval,
                "source": "alpaca",
            }
        )
    out.sort(key=lambda item: (item["symbol"], item["ts"]))
    return out


def _normalize_yahoo_chart(symbol: str, interval: str, payload):
    chart = payload.get("chart") if isinstance(payload, dict) else {}
    result = (chart or {}).get("result") or []
    if not result:
        return []
    first = result[0] if isinstance(result[0], dict) else {}
    timestamps = list(first.get("timestamp") or [])
    quote_rows = (((first.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    opens = list(quote_rows.get("open") or [])
    highs = list(quote_rows.get("high") or [])
    lows = list(quote_rows.get("low") or [])
    closes = list(quote_rows.get("close") or [])
    volumes = list(quote_rows.get("volume") or [])
    out = []
    for idx, ts in enumerate(timestamps):
        try:
            close_value = closes[idx]
        except IndexError:
            close_value = None
        if close_value is None:
            continue
        open_value = opens[idx] if idx < len(opens) else close_value
        high_value = highs[idx] if idx < len(highs) else None
        low_value = lows[idx] if idx < len(lows) else None
        volume_value = volumes[idx] if idx < len(volumes) else 0.0
        open_float = float(close_value if open_value is None else open_value)
        close_float = float(close_value)
        high_float = float(high_value) if high_value is not None else max(open_float, close_float)
        low_float = float(low_value) if low_value is not None else min(open_float, close_float)
        out.append(
            {
                "symbol": symbol,
                "ts": int(ts) * 1000,
                "o": open_float,
                "h": high_float,
                "l": low_float,
                "c": close_float,
                "v": float(volume_value or 0.0),
                "interval": interval,
                "source": "yahoo",
            }
        )
    out.sort(key=lambda item: (item["symbol"], item["ts"]))
    return out


def fetch_binance_klines(symbol: str, interval: str, limit: int, base_url: str, request_json=_http_get_json):
    params = urllib.parse.urlencode(
        {
            "symbol": symbol,
            "interval": interval,
            "limit": max(1, min(int(limit), 1000)),
        }
    )
    url = f"{base_url.rstrip('/')}/api/v3/klines?{params}"
    return _normalize_binance_klines(symbol, interval, request_json(url))


def fetch_bybit_klines(symbol: str, interval: str, limit: int, base_url: str, request_json=_http_get_json):
    interval_cfg = INTERVALS[interval]
    params = urllib.parse.urlencode(
        {
            "category": "linear",
            "symbol": symbol,
            "interval": interval_cfg["bybit_interval"],
            "limit": max(1, min(int(limit), 1000)),
        }
    )
    url = f"{base_url.rstrip('/')}/v5/market/kline?{params}"
    payload = request_json(url)
    rows = ((payload or {}).get("result") or {}).get("list") or []
    return _normalize_bybit_klines(symbol, interval, rows)


def fetch_kraken_klines(symbol: str, interval: str, limit: int, base_url: str, request_json=_http_get_json):
    interval_cfg = INTERVALS[interval]
    params = urllib.parse.urlencode(
        {
            "pair": symbol,
            "interval": interval_cfg["kraken_interval"],
        }
    )
    url = f"{base_url.rstrip('/')}/OHLC?{params}"
    payload = request_json(url)
    result = payload.get("result") if isinstance(payload, dict) else {}
    rows = []
    if isinstance(result, dict):
        for key, value in result.items():
            if key == "last":
                continue
            rows = value
            break
    normalized = _normalize_kraken_ohlc(symbol, interval, rows)
    if limit > 0:
        normalized = normalized[-max(1, int(limit)) :]
    return normalized


def fetch_alpaca_klines(symbol: str, interval: str, limit: int, base_url: str, request_json=_http_get_json):
    api_key, api_secret = _alpaca_credentials()
    if not api_key or not api_secret:
        raise RuntimeError(f"alpaca_credentials_missing symbol={symbol}")
    interval_cfg = INTERVALS[interval]
    params = urllib.parse.urlencode(
        {
            "symbols": symbol,
            "timeframe": interval_cfg["alpaca_timeframe"],
            "limit": max(1, min(int(limit), 10000)),
            "feed": os.getenv("OPENCLAW_ALPACA_FEED", "iex"),
            "sort": "asc",
        }
    )
    url = f"{base_url.rstrip('/')}/stocks/bars?{params}"
    payload = request_json(
        url,
        headers={
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        },
    )
    bars = ((payload or {}).get("bars") or {}).get(symbol) or []
    return _normalize_alpaca_bars(symbol, interval, bars)


def fetch_yahoo_klines(symbol: str, interval: str, limit: int, base_url: str, request_json=_http_get_json):
    interval_cfg = INTERVALS[interval]
    params = urllib.parse.urlencode(
        {
            "interval": interval_cfg["yahoo_interval"],
            "range": interval_cfg["yahoo_range"],
            "includePrePost": "false",
            "events": "div,splits",
        }
    )
    url = f"{base_url.rstrip('/')}/{urllib.parse.quote(symbol)}?{params}"
    normalized = _normalize_yahoo_chart(symbol, interval, request_json(url))
    if limit > 0:
        normalized = normalized[-max(1, int(limit)) :]
    return normalized


def fetch_public_klines(
    symbol: str,
    interval: str,
    limit: int,
    *,
    binance_base_url: str = DEFAULT_BINANCE_BASE_URL,
    bybit_base_url: str = DEFAULT_BYBIT_BASE_URL,
    kraken_base_url: str = DEFAULT_KRAKEN_BASE_URL,
    alpaca_data_base_url: str = DEFAULT_ALPACA_DATA_BASE_URL,
    yahoo_chart_base_url: str = DEFAULT_YAHOO_CHART_BASE_URL,
    request_json=_http_get_json,
):
    provider = classify_symbol_provider(symbol)
    if provider == "kraken_spot":
        return fetch_kraken_klines(symbol, interval, limit, kraken_base_url, request_json=request_json)
    if provider == "alpaca_equity":
        failures = []
        api_key, api_secret = _alpaca_credentials()
        if api_key and api_secret:
            try:
                rows = fetch_alpaca_klines(symbol, interval, limit, alpaca_data_base_url, request_json=request_json)
                if rows:
                    return rows
                failures.append("alpaca_empty")
            except Exception as exc:
                failures.append(f"alpaca:{type(exc).__name__}")
        else:
            failures.append("alpaca_credentials_missing")

        fallback_provider = resolve_public_equity_provider()
        if fallback_provider == "yahoo":
            try:
                rows = fetch_yahoo_klines(symbol, interval, limit, yahoo_chart_base_url, request_json=request_json)
                if rows:
                    return rows
                failures.append("yahoo_empty")
            except Exception as exc:
                failures.append(f"yahoo:{type(exc).__name__}")
        elif not fallback_provider and failures == ["alpaca_credentials_missing"]:
            raise RuntimeError(f"alpaca_credentials_missing symbol={symbol}")
        else:
            failures.append(f"unsupported_equity_provider:{fallback_provider or 'none'}")

        raise RuntimeError(
            f"equity_market_fetch_failed symbol={symbol} interval={interval} failures={','.join(failures)}"
        )

    failures = []
    try:
        rows = fetch_binance_klines(symbol, interval, limit, binance_base_url, request_json=request_json)
        if rows:
            return rows
        failures.append("binance_empty")
    except Exception as exc:  # pragma: no cover - exercised via fallback test
        failures.append(f"binance:{type(exc).__name__}")

    try:
        rows = fetch_bybit_klines(symbol, interval, limit, bybit_base_url, request_json=request_json)
        if rows:
            return rows
        failures.append("bybit_empty")
    except Exception as exc:  # pragma: no cover - exercised via fallback test
        failures.append(f"bybit:{type(exc).__name__}")

    raise RuntimeError(f"market_fetch_failed symbol={symbol} interval={interval} failures={','.join(failures)}")


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def merge_rows(existing, incoming):
    merged = {}
    for row in existing or []:
        symbol = row.get("symbol")
        ts = row.get("ts")
        if symbol is None or ts is None:
            continue
        merged[(symbol, int(ts))] = row
    for row in incoming or []:
        symbol = row.get("symbol")
        ts = row.get("ts")
        if symbol is None or ts is None:
            continue
        merged[(symbol, int(ts))] = row
    rows = list(merged.values())
    rows.sort(key=lambda item: (item["symbol"], int(item["ts"])))
    return rows


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def sync_interval(
    symbols,
    interval: str,
    *,
    limit: int,
    full: bool,
    market_dir: Path,
    fetcher=fetch_public_klines,
):
    target_path = market_dir / INTERVALS[interval]["file"]
    existing = [] if full else load_jsonl(target_path)
    new_rows = []
    skipped = []
    for symbol in symbols:
        try:
            rows = fetcher(symbol, interval, limit)
        except RuntimeError as exc:
            message = str(exc)
            if "alpaca_credentials_missing" in message or "equity_market_fetch_failed" in message:
                skipped.append({"symbol": symbol, "reason": message})
                continue
            raise
        new_rows.extend(rows)
    merged = merge_rows(existing, new_rows)
    write_jsonl(target_path, merged)
    return {
        "path": target_path,
        "symbols": len(symbols),
        "interval": interval,
        "fetched": len(new_rows),
        "stored": len(merged),
        "skipped": skipped,
    }


def run(
    *,
    config_path: Path,
    symbols=None,
    limit: int = 500,
    full: bool = False,
    market_dir: Path = MARKET_DIR,
    fetcher=fetch_public_klines,
):
    resolved_symbols = resolve_symbols(config_path, cli_symbols=symbols)
    if not resolved_symbols:
        raise RuntimeError(f"no symbols resolved from {config_path}")

    summaries = []
    started_at = int(time.time() * 1000)
    for interval in ("15m", "1h"):
        summaries.append(
            sync_interval(
                resolved_symbols,
                interval,
                limit=limit,
                full=full,
                market_dir=market_dir,
                fetcher=fetcher,
            )
        )

    for summary in summaries:
        try:
            rel_path = summary["path"].relative_to(REPO_ROOT)
        except ValueError:
            rel_path = summary["path"]
        print(
            f"{summary['interval']}: fetched={summary['fetched']} stored={summary['stored']} "
            f"symbols={summary['symbols']} path={rel_path}"
        )
        skipped = list(summary.get("skipped") or [])
        if skipped:
            skipped_symbols = ",".join(sorted({str(item.get('symbol') or '') for item in skipped if str(item.get('symbol') or '').strip()}))
            print(f"{summary['interval']}: skipped={len(skipped)} reason=credentials_missing symbols={skipped_symbols}")
    print(f"market_sync_ok started_at_ms={started_at} symbols={','.join(resolved_symbols)}")
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch public market candles for the trading sims")
    parser.add_argument("--config", type=str, default=None, help="Override trading config path")
    parser.add_argument("--symbol", action="append", default=None, help="Override config symbols (repeatable)")
    parser.add_argument("--limit", type=int, default=500, help="Max candles per symbol/timeframe to fetch")
    parser.add_argument("--full", action="store_true", help="Rewrite candle files from scratch")
    args = parser.parse_args(argv)

    config_path = resolve_path(args.config, CONFIG_ENV, DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        print(f"ERROR: config not found at {config_path}", file=sys.stderr)
        return 2

    try:
        run(
            config_path=config_path,
            symbols=args.symbol,
            limit=args.limit,
            full=args.full,
        )
    except (RuntimeError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
