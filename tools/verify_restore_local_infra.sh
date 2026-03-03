#!/usr/bin/env bash
set -euo pipefail

if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$REPO_ROOT"

TARGET="tools/restore_local_infra.sh"

if [ ! -f "$TARGET" ]; then
  echo "FAIL: missing $TARGET" >&2
  exit 1
fi

if [ ! -x "$TARGET" ]; then
  echo "FAIL: $TARGET is not executable" >&2
  exit 1
fi
echo "PASS: executable $TARGET"

bash -n "$TARGET"
echo "PASS: bash -n $TARGET"

TMP_OUT="$(mktemp)"
set +e
RESTORE_DRY_RUN=1 "$TARGET" >"$TMP_OUT" 2>&1
rc=$?
set -e

if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ] && [ "$rc" -ne 2 ]; then
  echo "FAIL: dry-run returned unexpected exit code: $rc" >&2
  sed -n '1,120p' "$TMP_OUT" >&2
  rm -f "$TMP_OUT"
  exit 1
fi

if ! grep -q "dry_run=1" "$TMP_OUT"; then
  echo "FAIL: dry-run output missing header marker" >&2
  sed -n '1,120p' "$TMP_OUT" >&2
  rm -f "$TMP_OUT"
  exit 1
fi

if ! grep -q "\\[DRY_RUN\\]" "$TMP_OUT"; then
  echo "FAIL: dry-run output missing [DRY_RUN] actions" >&2
  sed -n '1,120p' "$TMP_OUT" >&2
  rm -f "$TMP_OUT"
  exit 1
fi

echo "PASS: RESTORE_DRY_RUN=1 $TARGET (exit_code=$rc)"
rm -f "$TMP_OUT"
