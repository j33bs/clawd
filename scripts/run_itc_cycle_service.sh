#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MARKET_LIMIT="${OPENCLAW_ITC_MARKET_LIMIT:-300}"
MAX_LLM="${OPENCLAW_ITC_MAX_LLM:-80}"
CONFIG_PATH="${OPENCLAW_ITC_CONFIG_PATH:-}"
FEATURES_CONFIG_PATH="${OPENCLAW_ITC_FEATURES_CONFIG_PATH:-}"
MODEL_OVERRIDE="${OPENCLAW_ITC_MODEL:-}"
SIM_ID="${OPENCLAW_ITC_SIM_ID:-}"
RULES_ONLY="${OPENCLAW_ITC_RULES_ONLY:-0}"
FULL_REPROCESS="${OPENCLAW_ITC_FULL:-0}"
SKIP_MARKET="${OPENCLAW_ITC_SKIP_MARKET:-0}"
SYMBOLS_CSV="${OPENCLAW_ITC_SYMBOLS:-}"

args=(
  "--market-limit" "$MARKET_LIMIT"
  "--max-llm" "$MAX_LLM"
)

if [[ -n "$CONFIG_PATH" ]]; then
  args+=("--config" "$CONFIG_PATH")
fi

if [[ -n "$FEATURES_CONFIG_PATH" ]]; then
  args+=("--features-config" "$FEATURES_CONFIG_PATH")
fi

if [[ -n "$MODEL_OVERRIDE" ]]; then
  args+=("--model" "$MODEL_OVERRIDE")
fi

if [[ -n "$SIM_ID" ]]; then
  args+=("--sim" "$SIM_ID")
fi

if [[ "$RULES_ONLY" == "1" || "$RULES_ONLY" == "true" || "$RULES_ONLY" == "yes" ]]; then
  args+=("--rules-only")
fi

if [[ "$FULL_REPROCESS" == "1" || "$FULL_REPROCESS" == "true" || "$FULL_REPROCESS" == "yes" ]]; then
  args+=("--full")
fi

if [[ "$SKIP_MARKET" == "1" || "$SKIP_MARKET" == "true" || "$SKIP_MARKET" == "yes" ]]; then
  args+=("--skip-market")
fi

if [[ -n "$SYMBOLS_CSV" ]]; then
  IFS=',' read -r -a symbols <<< "$SYMBOLS_CSV"
  for symbol in "${symbols[@]}"; do
    symbol="$(printf '%s' "$symbol" | xargs)"
    [[ -n "$symbol" ]] && args+=("--symbol" "$symbol")
  done
fi

exec /usr/bin/env python3 "$ROOT_DIR/scripts/run_cycle.py" "${args[@]}"
