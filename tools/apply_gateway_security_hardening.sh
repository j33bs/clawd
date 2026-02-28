#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$ROOT/.runtime/openclaw}"
DIST_DIR="$RUNTIME_DIR/dist"

if [[ ! -d "$DIST_DIR" ]]; then
  echo "missing runtime dist directory: $DIST_DIR" >&2
  exit 1
fi

mapfile -t TARGET_FILES < <(find "$DIST_DIR" -maxdepth 1 -type f -name 'gateway-cli-*.js' | sort)
if [[ "${#TARGET_FILES[@]}" -eq 0 ]]; then
  echo "unable to find gateway-cli bundle under $DIST_DIR" >&2
  exit 1
fi

PATCH_TOOL="$ROOT/tools/gateway_security_hardening_patch.mjs"
if [[ ! -f "$PATCH_TOOL" ]]; then
  echo "missing patch tool: $PATCH_TOOL" >&2
  exit 1
fi

for target in "${TARGET_FILES[@]}"; do
  if [[ "${1:-}" == "--check" ]]; then
    node "$PATCH_TOOL" --file "$target" --check
  else
    node "$PATCH_TOOL" --file "$target"
  fi
done
