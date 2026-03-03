#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_SERVICE="${OPENCLAW_AGENT_SERVICE:-openclaw-gateway.service}"
LOG_DIR="${OPENCLAW_AGENT_WATCHDOG_LOG_DIR:-${ROOT}/reports/health}"
LOG_FILE="${LOG_DIR}/agent_watchdog.log"

mkdir -p "${LOG_DIR}"

ts() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_line() {
  printf '%s %s\n' "$(ts)" "$*" >>"${LOG_FILE}"
}

status_before="$(systemctl --user is-active "${TARGET_SERVICE}" 2>/dev/null || true)"
if [[ "${status_before}" == "active" ]]; then
  log_line "watchdog=ok service=${TARGET_SERVICE} state=${status_before}"
  exit 0
fi

log_line "watchdog=restart_attempt service=${TARGET_SERVICE} state_before=${status_before:-unknown}"
if ! systemctl --user restart "${TARGET_SERVICE}" >/dev/null 2>&1; then
  log_line "watchdog=restart_failed service=${TARGET_SERVICE}"
  exit 2
fi

status_after="$(systemctl --user is-active "${TARGET_SERVICE}" 2>/dev/null || true)"
if [[ "${status_after}" != "active" ]]; then
  log_line "watchdog=restart_unhealthy service=${TARGET_SERVICE} state_after=${status_after:-unknown}"
  exit 3
fi

log_line "watchdog=restart_success service=${TARGET_SERVICE} state_after=${status_after}"
exit 0
