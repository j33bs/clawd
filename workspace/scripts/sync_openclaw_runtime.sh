#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$ROOT/.runtime/openclaw}"
REBUILD_SCRIPT="${OPENCLAW_REBUILD_SCRIPT:-$ROOT/workspace/scripts/rebuild_runtime_openclaw.sh}"
REBUILD_MODE="${OPENCLAW_RUNTIME_SYNC_MODE:-LIVEWIRE}"
STAMP_FILE="${OPENCLAW_BUILD_STAMP_FILE:-$HOME/.local/share/openclaw-build/version_build.json}"
MODE="${1:-sync}"

resolve_source_dir() {
  if [[ -n "${OPENCLAW_SOURCE_DIR:-}" ]]; then
    printf '%s\n' "$OPENCLAW_SOURCE_DIR"
    return 0
  fi

  if [[ -n "${OPENCLAW_PACKAGE_BIN:-}" ]]; then
    readlink -f "$OPENCLAW_PACKAGE_BIN"
    return 0
  fi

  if [[ -x /usr/bin/openclaw ]]; then
    readlink -f /usr/bin/openclaw
    return 0
  fi

  return 1
}

package_dir_from_bin() {
  local resolved_bin="$1"
  dirname "$resolved_bin"
}

json_field() {
  local json_file="$1"
  local field="$2"
  node -e 'const fs=require("fs"); const file=process.argv[1]; const key=process.argv[2]; const data=JSON.parse(fs.readFileSync(file,"utf8")); const value=data?.[key]; if (value !== undefined && value !== null) process.stdout.write(String(value));' "$json_file" "$field"
}

sync_build_stamp_version() {
  local version="$1"
  local stamp_dir
  stamp_dir="$(dirname "$STAMP_FILE")"
  mkdir -p "$stamp_dir"
  node -e 'const fs=require("fs"); const file=process.argv[1]; const version=process.argv[2]; let data={}; try { data=JSON.parse(fs.readFileSync(file,"utf8")); } catch {} data.package_version=version; fs.writeFileSync(file, JSON.stringify(data));' "$STAMP_FILE" "$version"
}

SOURCE_BIN="$(resolve_source_dir)"
SOURCE_DIR="$(package_dir_from_bin "$SOURCE_BIN")"
SOURCE_PACKAGE_JSON="$SOURCE_DIR/package.json"
RUNTIME_PACKAGE_JSON="$RUNTIME_DIR/package.json"

if [[ ! -f "$SOURCE_PACKAGE_JSON" ]]; then
  echo "runtime_sync: source package.json missing at $SOURCE_PACKAGE_JSON" >&2
  exit 1
fi

SOURCE_VERSION="$(json_field "$SOURCE_PACKAGE_JSON" version)"
RUNTIME_VERSION=""
if [[ -f "$RUNTIME_PACKAGE_JSON" ]]; then
  RUNTIME_VERSION="$(json_field "$RUNTIME_PACKAGE_JSON" version)"
fi

if [[ "$MODE" == "--check" ]]; then
  if [[ -n "$RUNTIME_VERSION" && "$SOURCE_VERSION" == "$RUNTIME_VERSION" ]]; then
    echo "runtime_sync: in_sync source=$SOURCE_VERSION runtime=$RUNTIME_VERSION"
  else
    echo "runtime_sync: drift source=$SOURCE_VERSION runtime=${RUNTIME_VERSION:-missing}"
  fi
  exit 0
fi

if [[ -n "$RUNTIME_VERSION" && "$SOURCE_VERSION" == "$RUNTIME_VERSION" ]]; then
  sync_build_stamp_version "$SOURCE_VERSION"
  exit 0
fi

if [[ ! -x "$REBUILD_SCRIPT" ]]; then
  echo "runtime_sync: rebuild script missing at $REBUILD_SCRIPT" >&2
  exit 1
fi

echo "runtime_sync: rebuild start source=$SOURCE_VERSION runtime=${RUNTIME_VERSION:-missing}" >&2
OPENCLAW_SOURCE_DIR="$SOURCE_DIR" \
OPENCLAW_RUNTIME_DIR="$RUNTIME_DIR" \
MODE="$REBUILD_MODE" \
bash "$REBUILD_SCRIPT"

UPDATED_RUNTIME_VERSION="$(json_field "$RUNTIME_PACKAGE_JSON" version)"
if [[ "$UPDATED_RUNTIME_VERSION" != "$SOURCE_VERSION" ]]; then
  echo "runtime_sync: rebuild verification failed source=$SOURCE_VERSION runtime=$UPDATED_RUNTIME_VERSION" >&2
  exit 1
fi

sync_build_stamp_version "$UPDATED_RUNTIME_VERSION"
echo "runtime_sync: rebuild complete version=$UPDATED_RUNTIME_VERSION" >&2
