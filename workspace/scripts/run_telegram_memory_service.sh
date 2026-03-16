#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${HOME}/.config/openclaw/telegram-memory.env"

if [[ -f "${ENV_FILE}" ]]; then
  while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    export "${key}"="${value}"
  done < "${ENV_FILE}"
fi

cd "${HOME}/src/clawd"
exec /usr/bin/env python3 workspace/scripts/telegram_memory_telethon.py --backfill "${OPENCLAW_TELEGRAM_MEMORY_BACKFILL:-500}"
