#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DIR="${OPENCLAW_SOURCE_DIR:-/usr/lib/node_modules/openclaw}"
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$ROOT/.runtime/openclaw}"
INDEX_FILE="$RUNTIME_DIR/dist/index.js"
HARDENING_SRC_DIR="$ROOT/workspace/runtime_hardening/src"
HARDENING_TARGET_DIR="$RUNTIME_DIR/dist/hardening"
OVERLAY_SRC_FILE="$ROOT/workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs"
OVERLAY_TARGET_FILE="$RUNTIME_DIR/dist/runtime_hardening_overlay.mjs"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "missing source runtime directory: $SOURCE_DIR" >&2
  exit 1
fi

if [[ ! -d "$HARDENING_SRC_DIR" ]]; then
  echo "missing hardening source directory: $HARDENING_SRC_DIR" >&2
  exit 1
fi

if [[ ! -f "$OVERLAY_SRC_FILE" ]]; then
  echo "missing runtime overlay file: $OVERLAY_SRC_FILE" >&2
  exit 1
fi

echo "repo_sha=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "source=$SOURCE_DIR"
echo "target=$RUNTIME_DIR"

mkdir -p "$RUNTIME_DIR"
rsync -a --delete "$SOURCE_DIR/" "$RUNTIME_DIR/"

mkdir -p "$HARDENING_TARGET_DIR/security"
cp "$HARDENING_SRC_DIR"/*.mjs "$HARDENING_TARGET_DIR/"
cp "$HARDENING_SRC_DIR"/security/*.mjs "$HARDENING_TARGET_DIR/security/"
cp "$OVERLAY_SRC_FILE" "$OVERLAY_TARGET_FILE"

if [[ ! -f "$INDEX_FILE" ]]; then
  echo "runtime index missing after copy: $INDEX_FILE" >&2
  exit 1
fi

if ! head -n 12 "$INDEX_FILE" | rg -q 'runtime_hardening_overlay\.mjs'; then
  tmp="$(mktemp)"
  if head -n 1 "$INDEX_FILE" | rg -q '^#!'; then
    {
      head -n 1 "$INDEX_FILE"
      echo 'import "./runtime_hardening_overlay.mjs";'
      tail -n +2 "$INDEX_FILE"
    } > "$tmp"
  else
    {
      echo 'import "./runtime_hardening_overlay.mjs";'
      cat "$INDEX_FILE"
    } > "$tmp"
  fi
  mv "$tmp" "$INDEX_FILE"
fi

echo "marker_check_runtime_dist:"
rg -n -S "runtime_hardening_overlay|runtime_hardening_initialized|Invalid runtime hardening configuration" "$RUNTIME_DIR/dist" || true
