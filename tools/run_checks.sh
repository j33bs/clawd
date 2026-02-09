#!/usr/bin/env bash
set -euo pipefail

python3 tools/check_ignored_tracking.py
python3 -m unittest discover -s tests_unittest
python3 tools/preflight_trading_env.py
python3 tools/regression_guard.py
