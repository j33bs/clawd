#!/usr/bin/env bash
# Idempotent installer for tracked git hooks (pre-commit/pre-push).
set -euo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: not inside a git repository"
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

bash workspace/scripts/install-hooks.sh

echo "OK: pre-commit will run workspace/scripts/scan_audit_secrets.sh for staged workspace/audit files."
