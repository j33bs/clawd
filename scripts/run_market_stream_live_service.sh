#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKFILL_LIMIT="${OPENCLAW_MARKET_STREAM_BACKFILL_LIMIT:-300}"
TICK_LOOKBACK_MS="${OPENCLAW_MARKET_STREAM_TICK_LOOKBACK_MS:-300000}"
FLUSH_INTERVAL_SEC="${OPENCLAW_MARKET_STREAM_FLUSH_INTERVAL_SEC:-2.0}"
RECONNECT_SEC="${OPENCLAW_MARKET_STREAM_RECONNECT_SEC:-5.0}"
CONFIG_PATH="${OPENCLAW_MARKET_STREAM_CONFIG_PATH:-}"
SYMBOLS_CSV="${OPENCLAW_MARKET_STREAM_SYMBOLS:-}"

args=(
  "--backfill-limit" "$BACKFILL_LIMIT"
  "--tick-lookback-ms" "$TICK_LOOKBACK_MS"
  "--flush-interval-sec" "$FLUSH_INTERVAL_SEC"
  "--reconnect-sec" "$RECONNECT_SEC"
)

if [[ -n "$CONFIG_PATH" ]]; then
  args+=("--config" "$CONFIG_PATH")
fi

if [[ -n "$SYMBOLS_CSV" ]]; then
  IFS=',' read -r -a symbols <<< "$SYMBOLS_CSV"
  for symbol in "${symbols[@]}"; do
    symbol="$(printf '%s' "$symbol" | xargs)"
    [[ -n "$symbol" ]] && args+=("--symbol" "$symbol")
  done
fi

exec /usr/bin/env python3 "$ROOT_DIR/scripts/market_stream_live.py" "${args[@]}"
