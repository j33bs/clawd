#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$SCRIPT_DIR/.build/release/CoreMLEmbedRunner"
if [ ! -x "$BIN" ]; then
  BIN="$($SCRIPT_DIR/build.sh)"
fi
ARGS=("$@")
if [ "${#ARGS[@]}" -gt 0 ] && [ "${ARGS[0]}" = "--json" ]; then
  ARGS=("${ARGS[@]:1}")
fi
if [ "${#ARGS[@]}" -eq 0 ]; then
  exec "$BIN"
fi
exec "$BIN" "${ARGS[@]}"
