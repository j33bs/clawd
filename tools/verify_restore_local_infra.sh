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

TMP_OUT_FORCE="$(mktemp)"
set +e
RESTORE_DRY_RUN=1 \
RESTORE_FORCE_RESTORE_PATHS="tools/qmd_mcp_start_ipv4.sh,tools/install_launchagent_ain.sh,workspace/launchd/ai.openclaw.ain.plist" \
"$TARGET" >"$TMP_OUT_FORCE" 2>&1
rc_force=$?
set -e

if [ "$rc_force" -ne 0 ] && [ "$rc_force" -ne 1 ] && [ "$rc_force" -ne 2 ]; then
  echo "FAIL: forced self-heal dry-run returned unexpected exit code: $rc_force" >&2
  sed -n '1,160p' "$TMP_OUT_FORCE" >&2
  rm -f "$TMP_OUT_FORCE"
  exit 1
fi

if ! grep -q "\\[DRY_RUN\\] would restore tools/qmd_mcp_start_ipv4.sh from 511a4db716dfe12da62036bbf149a481a95fc76d" "$TMP_OUT_FORCE"; then
  echo "FAIL: forced self-heal dry-run did not print expected restore line for qmd helper" >&2
  sed -n '1,200p' "$TMP_OUT_FORCE" >&2
  rm -f "$TMP_OUT_FORCE"
  exit 1
fi

echo "PASS: forced self-heal dry-run emits pinned-commit restore attempts (exit_code=$rc_force)"
rm -f "$TMP_OUT_FORCE"

TMP_OUT_PIN="$(mktemp)"
PIN_OVERRIDE="511a4db716dfe12da62036bbf149a481a95fc76d"
set +e
INFRA_PINNED_COMMIT="$PIN_OVERRIDE" \
RESTORE_DRY_RUN=1 \
RESTORE_FORCE_RESTORE_PATHS="tools/qmd_mcp_start_ipv4.sh" \
"$TARGET" >"$TMP_OUT_PIN" 2>&1
rc_pin=$?
set -e

if [ "$rc_pin" -ne 0 ] && [ "$rc_pin" -ne 1 ] && [ "$rc_pin" -ne 2 ]; then
  echo "FAIL: pinned-override dry-run returned unexpected exit code: $rc_pin" >&2
  sed -n '1,160p' "$TMP_OUT_PIN" >&2
  rm -f "$TMP_OUT_PIN"
  exit 1
fi

if ! grep -q "\\[DRY_RUN\\] would restore tools/qmd_mcp_start_ipv4.sh from $PIN_OVERRIDE" "$TMP_OUT_PIN"; then
  echo "FAIL: INFRA_PINNED_COMMIT override not reflected in restore output" >&2
  sed -n '1,200p' "$TMP_OUT_PIN" >&2
  rm -f "$TMP_OUT_PIN"
  exit 1
fi

echo "PASS: INFRA_PINNED_COMMIT override respected in dry-run (exit_code=$rc_pin)"
rm -f "$TMP_OUT_PIN"
