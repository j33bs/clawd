#!/usr/bin/env bash
# Fail if protected changes are present without a governance log update.
set -euo pipefail

LOG_FILE="workspace/governance/GOVERNANCE_LOG.md"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "FAIL governance: missing $LOG_FILE"
  exit 1
fi

BASE="${1:-}"
HEAD="${2:-}"

if [[ -n "$BASE" && -n "$HEAD" ]]; then
  CHANGED_FILES=$(git diff --name-only "$BASE" "$HEAD" || true)
elif [[ -n "$(git status --porcelain --untracked-files=no 2>/dev/null || true)" ]]; then
  CHANGED_FILES=$( (git diff --name-only; git diff --name-only --cached) | sed '/^$/d' | sort -u || true)
elif git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
  CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD || true)
else
  CHANGED_FILES=$(git diff --name-only --cached || true)
fi

if [[ -z "${CHANGED_FILES//[[:space:]]/}" ]]; then
  echo "PASS governance: no changes to evaluate"
  exit 0
fi

PROTECTED_REGEX='^(core/system2/|workspace/governance/|workspace/source-ui/|workspace/scripts/policy_router\.py|scripts/openclaw_secrets_cli\.js)'
PROTECTED_CHANGED=$(printf '%s\n' "$CHANGED_FILES" | rg -n "$PROTECTED_REGEX" --no-line-number || true)

if [[ -z "${PROTECTED_CHANGED//[[:space:]]/}" ]]; then
  echo "PASS governance: no protected paths changed"
  exit 0
fi

if printf '%s\n' "$CHANGED_FILES" | rg -q '^workspace/governance/GOVERNANCE_LOG\.md$'; then
  echo "PASS governance: protected changes include governance log update"
  exit 0
fi

echo "FAIL governance: protected changes require workspace/governance/GOVERNANCE_LOG.md update"
echo "Protected changes detected:"
printf '%s\n' "$PROTECTED_CHANGED"
exit 1
