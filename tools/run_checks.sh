#!/usr/bin/env bash
set -euo pipefail

# Local usage:
#   OPENCLAW_LOCAL_GATES=1 tools/run_checks.sh
# Local gates enforce launchagent alignment and machine-surface contract tripwire.
if [[ "${OPENCLAW_LOCAL_GATES:-0}" == "1" ]]; then
  echo "[local-gates] enabled"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "[local-gates] checking launchagent alignment"
    if ! tools/check_launchagent_points_to_repo.sh; then
      echo "[local-gates] FAIL launchagent alignment (see tools/check_launchagent_points_to_repo.sh)" >&2
      exit 1
    fi
    echo "[local-gates] PASS launchagent alignment"

    echo "[local-gates] running machine-surface tripwire"
    if ! tools/reliability_tripwire.sh; then
      echo "[local-gates] FAIL machine-surface tripwire (see tools/reliability_tripwire.sh)" >&2
      exit 1
    fi
    echo "[local-gates] PASS machine-surface tripwire"
  else
    echo "[local-gates] skipped (non-macOS)"
  fi
fi

python3 tools/check_ignored_tracking.py
python3 -m unittest discover -s tests_unittest
python3 tools/preflight_trading_env.py
python3 tools/regression_guard.py
