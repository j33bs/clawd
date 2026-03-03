#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
swift build -c release >&2
BIN="$SCRIPT_DIR/.build/release/CoreMLEmbedRunner"
if [ ! -x "$BIN" ]; then
  echo "build did not produce executable: $BIN" >&2
  exit 1
fi
printf '%s\n' "$BIN"
