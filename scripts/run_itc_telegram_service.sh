#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKFILL="${OPENCLAW_ITC_TELEGRAM_BACKFILL:-50}"
DRY_RUN="${OPENCLAW_ITC_TELEGRAM_DRY_RUN:-0}"
RECONFIGURE="${OPENCLAW_ITC_TELEGRAM_RECONFIGURE:-0}"

args=(
  "--backfill" "$BACKFILL"
)

if [[ "$DRY_RUN" == "1" || "$DRY_RUN" == "true" || "$DRY_RUN" == "yes" ]]; then
  args+=("--dry-run")
fi

if [[ "$RECONFIGURE" == "1" || "$RECONFIGURE" == "true" || "$RECONFIGURE" == "yes" ]]; then
  args+=("--reconfigure")
fi

exec /usr/bin/env python3 "$ROOT_DIR/scripts/telethon_ingest.py" "${args[@]}"
