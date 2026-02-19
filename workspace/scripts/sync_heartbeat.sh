#!/usr/bin/env sh
set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
CANONICAL_HEARTBEAT="$REPO_ROOT/workspace/governance/HEARTBEAT.md"
ROOT_HEARTBEAT="$REPO_ROOT/HEARTBEAT.md"

fail() {
  printf '%s\n' "heartbeat sync guard: FAIL: $1" >&2
  exit 2
}

if [ ! -f "$CANONICAL_HEARTBEAT" ]; then
  fail "missing canonical file: $CANONICAL_HEARTBEAT"
fi

if ! git -C "$REPO_ROOT" ls-files --error-unmatch HEARTBEAT.md >/dev/null 2>&1; then
  fail "repo-root HEARTBEAT.md must be tracked"
fi

cp "$CANONICAL_HEARTBEAT" "$ROOT_HEARTBEAT"

if ! cmp -s "$CANONICAL_HEARTBEAT" "$ROOT_HEARTBEAT"; then
  fail "repo-root HEARTBEAT.md is not byte-identical to canonical after sync"
fi

printf '%s\n' "heartbeat sync guard: ok canonical=$CANONICAL_HEARTBEAT mirror=$ROOT_HEARTBEAT"

