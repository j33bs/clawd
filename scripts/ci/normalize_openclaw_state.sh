#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${REPO_ROOT}/.openclaw"
STATE_FILE="${STATE_DIR}/workspace-state.json"

mkdir -p "${STATE_DIR}"

if [ -L "${STATE_FILE}" ] || { [ -e "${STATE_FILE}" ] && [ ! -f "${STATE_FILE}" ]; }; then
  echo "normalize_openclaw_state: removing non-regular ${STATE_FILE}"
  rm -rf "${STATE_FILE}"
fi

if [ "${OPENCLAW_STATE_FILE_INIT:-0}" = "1" ] && [ ! -e "${STATE_FILE}" ]; then
  echo "{}" > "${STATE_FILE}"
  echo "normalize_openclaw_state: initialized ${STATE_FILE}"
fi

echo "normalize_openclaw_state: ok"
