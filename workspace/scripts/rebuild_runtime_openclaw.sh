#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DIR="${OPENCLAW_SOURCE_DIR:-/usr/lib/node_modules/openclaw}"
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$ROOT/.runtime/openclaw}"
ENTRY_FILE_JS="$RUNTIME_DIR/dist/entry.js"
ENTRY_FILE_MJS="$RUNTIME_DIR/dist/entry.mjs"
INDEX_FILE="$RUNTIME_DIR/dist/index.js"
HARDENING_SRC_DIR="$ROOT/workspace/runtime_hardening/src"
HARDENING_TARGET_DIR="$RUNTIME_DIR/dist/hardening"
OVERLAY_SRC_FILE="$ROOT/workspace/runtime_hardening/overlay/runtime_hardening_overlay.mjs"
OVERLAY_TARGET_FILE="$RUNTIME_DIR/dist/runtime_hardening_overlay.mjs"
MEMORY_MAINTENANCE_SCRIPT="$ROOT/workspace/scripts/memory_maintenance.py"
MEMORY_SNAPSHOT_BEFORE_REBUILD="${OPENCLAW_MEMORY_SNAPSHOT_BEFORE_REBUILD:-1}"
VLLM_HEALTH_GATE_SCRIPT="$ROOT/workspace/scripts/vllm_health_gate.sh"
OPENCLAW_VLLM_PREFLIGHT="${OPENCLAW_VLLM_PREFLIGHT:-0}"

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

if [[ "$OPENCLAW_VLLM_PREFLIGHT" == "1" ]]; then
  if [[ -f "$VLLM_HEALTH_GATE_SCRIPT" ]]; then
    echo "vllm_preflight=enabled"
    bash "$VLLM_HEALTH_GATE_SCRIPT" --preflight
  else
    echo "warning: vLLM health gate missing at $VLLM_HEALTH_GATE_SCRIPT" >&2
  fi
fi

if [[ "$MEMORY_SNAPSHOT_BEFORE_REBUILD" == "1" ]] && [[ -f "$MEMORY_MAINTENANCE_SCRIPT" ]]; then
  set +e
  snapshot_json="$(python3 "$MEMORY_MAINTENANCE_SCRIPT" --repo-root "$ROOT" snapshot --label runtime-rebuild --include-memory-md 2>&1)"
  snapshot_ec=$?
  set -e
  if [[ $snapshot_ec -eq 0 ]]; then
    echo "memory_snapshot=$snapshot_json"
  else
    echo "warning: memory snapshot failed before rebuild: $snapshot_json" >&2
  fi
fi

mkdir -p "$RUNTIME_DIR"
rsync -a --delete "$SOURCE_DIR/" "$RUNTIME_DIR/"

mkdir -p "$HARDENING_TARGET_DIR/security"
cp "$HARDENING_SRC_DIR"/*.mjs "$HARDENING_TARGET_DIR/"
cp "$HARDENING_SRC_DIR"/security/*.mjs "$HARDENING_TARGET_DIR/security/"
cp "$OVERLAY_SRC_FILE" "$OVERLAY_TARGET_FILE"

if [[ ! -f "$INDEX_FILE" ]]; then
  echo "runtime index missing after copy: $INDEX_FILE" >&2
fi

inject_overlay_import() {
  local target_file="$1"
  if [[ ! -f "$target_file" ]]; then
    return 0
  fi
  if head -n 16 "$target_file" | rg -q 'runtime_hardening_overlay\.mjs'; then
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  if head -n 1 "$target_file" | rg -q '^#!'; then
    {
      head -n 1 "$target_file"
      echo 'import "./runtime_hardening_overlay.mjs";'
      tail -n +2 "$target_file"
    } > "$tmp"
  else
    {
      echo 'import "./runtime_hardening_overlay.mjs";'
      cat "$target_file"
    } > "$tmp"
  fi
  mv "$tmp" "$target_file"
}

overlay_injected=0
for candidate in "$ENTRY_FILE_JS" "$ENTRY_FILE_MJS" "$INDEX_FILE"; do
  if [[ -f "$candidate" ]]; then
    inject_overlay_import "$candidate"
    overlay_injected=1
  fi
done

if [[ "$overlay_injected" -eq 0 ]]; then
  echo "runtime entry files missing after copy: expected one of $ENTRY_FILE_JS, $ENTRY_FILE_MJS, $INDEX_FILE" >&2
  exit 1
fi

echo "marker_check_runtime_dist:"
rg -n -S "runtime_hardening_overlay|runtime_hardening_initialized|Invalid runtime hardening configuration" "$RUNTIME_DIR/dist" || true
