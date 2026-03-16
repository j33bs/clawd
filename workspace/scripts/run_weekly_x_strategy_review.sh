#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${OPENCLAW_WEEKLY_X_PYTHON:-}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x /opt/homebrew/bin/python3 ]]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

exec "${PYTHON_BIN}" "${ROOT_DIR}/workspace/scripts/weekly_x_strategy_review.py" "$@"
