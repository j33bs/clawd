#!/usr/bin/env bash
set -euo pipefail

LOG_PATH=""
SINCE=""

usage() {
  echo "Usage: $0 --log <path> [--since <string>]" >&2
  echo "Example: $0 --log /tmp/openclaw/openclaw-2026-02-22.log --since \"2026-02-22 07:00:00\"" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --log) LOG_PATH="$2"; shift 2;;
    --since) SINCE="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

[[ -n "${LOG_PATH}" ]] || { usage; exit 2; }
[[ -f "${LOG_PATH}" ]] || { echo "FAIL: log not found: ${LOG_PATH}" >&2; exit 2; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

if [[ -n "${SINCE}" ]]; then
  if grep -Fq "$SINCE" "$LOG_PATH"; then
    awk -v since="$SINCE" '
      found { print }
      index($0, since) { found=1; print }
    ' "$LOG_PATH" > "$tmp"
  else
    echo "WARN: --since marker not found in log; scanning full file" >&2
    cp "$LOG_PATH" "$tmp"
  fi
else
  cp "$LOG_PATH" "$tmp"
fi

timeouts="$(grep -nE 'Telegram handler timed out|tg-mlw.*timed out' "$tmp" || true)"
deferred="$(grep -nE 'telegram_handler_deferred' "$tmp" || true)"
deadfail="$(grep -nE 'telegram_deadletter_write_failed|deadletter_write_failed|mkdirSync is not a function' "$tmp" || true)"

t_count="$(printf '%s\n' "$timeouts" | sed '/^\s*$/d' | wc -l | tr -d ' ')"
d_count="$(printf '%s\n' "$deferred" | sed '/^\s*$/d' | wc -l | tr -d ' ')"
f_count="$(printf '%s\n' "$deadfail" | sed '/^\s*$/d' | wc -l | tr -d ' ')"

echo "telegram live window verification"
echo "  log:   $LOG_PATH"
echo "  since: ${SINCE:-<start-of-log>}"
echo
echo "counts:"
echo "  timeouts:   $t_count"
echo "  deferred:   $d_count"
echo "  deadletter failures: $f_count"
echo

if [[ "$t_count" -gt 0 ]]; then
  echo "FAIL: handler timeouts detected" >&2
  echo "$timeouts" | head -n 50 >&2
  exit 1
fi

if [[ "$f_count" -gt 0 ]]; then
  echo "FAIL: deadletter failures detected" >&2
  echo "$deadfail" | head -n 50 >&2
  exit 1
fi

echo "PASS: no timeouts/deadletter failures detected in window"
exit 0
