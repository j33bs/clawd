#!/bin/bash
# Installs tracked Git hooks into .git/hooks.
#
# Rationale: Git does not track .git/hooks/* by default; this script makes hooks governed
# by installing from workspace/scripts/hooks/*.

set -euo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: not inside a git repository"
  exit 1
fi

HOOK_SRC_DIR="workspace/scripts/hooks"
HOOK_DST_DIR="$(git rev-parse --git-dir)/hooks"

install_one() {
  local name="$1"
  local src="${HOOK_SRC_DIR}/${name}"
  local dst="${HOOK_DST_DIR}/${name}"

  if [ ! -f "$src" ]; then
    echo "ERROR: missing hook template: $src"
    exit 1
  fi

  mkdir -p "$HOOK_DST_DIR"
  cp -f "$src" "$dst"
  chmod +x "$dst" || true
  echo "Installed: $dst"
}

install_one "pre-commit"
install_one "pre-push"

echo "OK: hooks installed from ${HOOK_SRC_DIR}"

