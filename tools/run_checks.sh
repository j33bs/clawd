#!/usr/bin/env bash
set -euo pipefail

if [[ "${OPENCLAW_LOCAL_GATES:-0}" == "1" ]] && [[ "$(uname -s)" == "Darwin" ]]; then
  if ! tools/check_launchagent_points_to_repo.sh; then
    echo "LaunchAgent misaligned: gateway not running repo wrapper; see tools/check_launchagent_points_to_repo.sh" >&2
    exit 1
  fi
fi

python3 tools/check_ignored_tracking.py
python3 -m unittest discover -s tests_unittest
python3 tools/preflight_trading_env.py
python3 tools/regression_guard.py
