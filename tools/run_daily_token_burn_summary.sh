#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_PATH="$ROOT/workspace/logs/token_usage.jsonl"
OUT_DIR="$ROOT/workspace/audit"
OUT_FILE="$OUT_DIR/token_burn_daily_$(date +%F).md"

mkdir -p "$OUT_DIR"

if [[ -s "$LOG_PATH" ]]; then
  if node "$ROOT/tools/summarize_token_usage.js" "$LOG_PATH" > "$OUT_FILE" 2>&1; then
    printf 'Wrote %s\n' "$OUT_FILE"
  else
    {
      printf 'Token burn summary failed at %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf 'Input log: %s\n' "$LOG_PATH"
      printf 'summarize_token_usage.js returned non-zero; see previous scheduler logs for details.\n'
    } > "$OUT_FILE"
  fi
else
  {
    printf 'Token burn summary skipped at %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'token_usage.jsonl missing or empty: %s\n' "$LOG_PATH"
  } > "$OUT_FILE"
fi

exit 0
