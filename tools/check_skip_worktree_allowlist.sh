#!/bin/sh
# Verify skip-worktree entries are restricted to an explicit allowlist.
# Usage: ./tools/check_skip_worktree_allowlist.sh

set -eu

ALLOWED_PATH="workspace/state/tacti_cr/events.jsonl"
SKIP_PATHS="$(git ls-files -v | awk '$1 ~ /^S/ {print $2}')"

if [ -z "$SKIP_PATHS" ]; then
  echo "skip-worktree allowlist check: ok (no skip-worktree entries)"
  exit 0
fi

VIOLATIONS=0
for path in $SKIP_PATHS; do
  if [ "$path" != "$ALLOWED_PATH" ]; then
    if [ "$VIOLATIONS" -eq 0 ]; then
      echo "skip-worktree allowlist violation(s):"
    fi
    echo "  $path"
    VIOLATIONS=1
  fi
done

if [ "$VIOLATIONS" -ne 0 ]; then
  exit 2
fi

echo "skip-worktree allowlist check: ok"
