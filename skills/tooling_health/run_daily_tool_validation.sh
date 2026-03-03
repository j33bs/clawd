#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${ROOT}/reports/automation"
LOG_FILE="${LOG_DIR}/tool_validation.log"

mkdir -p "${LOG_DIR}"

{
  printf '[%s] start tool validation\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  set +e
  python3 "${SCRIPT_DIR}/validate_tools_daily.py" --repo-root "${ROOT}"
  rc=$?
  set -e
  printf '[%s] done tool validation rc=%s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "${rc}"
  exit "${rc}"
} >>"${LOG_FILE}" 2>&1
