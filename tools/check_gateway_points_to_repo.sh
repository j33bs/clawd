#!/usr/bin/env bash
set -euo pipefail

# Verifies the user gateway unit resolves to the repo wrapper and repo working dir.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UNIT_NAME="${1:-openclaw-gateway.service}"
EXPECTED_RUNNER="${REPO_ROOT}/scripts/run_openclaw_gateway_repo_dali.sh"
EXPECTED_WD="${REPO_ROOT}"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "SKIP: systemctl not found"
  exit 0
fi

if ! SHOW_OUT="$(systemctl --user show "${UNIT_NAME}" -p ExecStart -p WorkingDirectory 2>/dev/null)"; then
  echo "SKIP: unable to query user systemd for ${UNIT_NAME}"
  exit 0
fi

EXECSTART_LINE="$(printf '%s\n' "${SHOW_OUT}" | awk '/^ExecStart=/{sub(/^ExecStart=/,""); print}')"
WORKDIR_LINE="$(printf '%s\n' "${SHOW_OUT}" | awk '/^WorkingDirectory=/{sub(/^WorkingDirectory=/,""); print}')"
WORKDIR_CLEAN="${WORKDIR_LINE#!}"

if [[ "${EXECSTART_LINE}" != *"${EXPECTED_RUNNER}"* ]]; then
  echo "FAIL: ${UNIT_NAME} ExecStart does not point to repo runner"
  echo "  expected contains: ${EXPECTED_RUNNER}"
  echo "  actual: ${EXECSTART_LINE}"
  exit 1
fi

if [[ "${WORKDIR_CLEAN}" != "${EXPECTED_WD}" ]]; then
  echo "FAIL: ${UNIT_NAME} WorkingDirectory mismatch"
  echo "  expected: ${EXPECTED_WD}"
  echo "  actual: ${WORKDIR_LINE}"
  exit 1
fi

echo "ok: ${UNIT_NAME} points to repo runner"
