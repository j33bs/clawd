#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOCK_DIR="${ROOT}/.runtime/locks"
LOG_DIR="${ROOT}/reports/automation"
LOG_FILE="${LOG_DIR}/memory_distill.log"
LOCK_FILE="${LOCK_DIR}/memory_distill.lock"

mkdir -p "${LOCK_DIR}" "${LOG_DIR}"

{
  flock -n 9 || {
    printf '[%s] skip: memory distill already running\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    exit 0
  }
  printf '[%s] start memory distill\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  python3 "${ROOT}/workspace/scripts/memory_distill_cron.py" --repo-root "${ROOT}"
  printf '[%s] done memory distill\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
