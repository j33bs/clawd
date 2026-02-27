#!/bin/bash
set -e

if ! command -v python3 >/dev/null 2>&1; then
    echo "FAIL: python3 not found. Install Python 3 and retry."
    exit 1
fi

python3 workspace/scripts/preflight_check.py
./tools/check_skip_worktree_allowlist.sh

echo "ok"
