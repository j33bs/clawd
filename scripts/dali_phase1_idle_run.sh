#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_ROOT="${DALI_FISHTANK_UE5_ENGINE_ROOT:-$ROOT_DIR/.runtime/UnrealEngine-5.6}"
PROJECT_PATH="${DALI_FISHTANK_UE5_PROJECT:-$ROOT_DIR/workspace/dali_unreal/DaliMirror.uproject}"
UE_CMD="${DALI_FISHTANK_UE5_EDITOR_CMD:-$ENGINE_ROOT/Engine/Binaries/Linux/UnrealEditor-Cmd}"
COMMANDLET_NAME="${DALI_FISHTANK_PHASE1_COMMANDLET:-ConsciousnessMirrorPhaseOneGenerate}"
OUTPUT_ROOT="${DALI_FISHTANK_PHASE1_OUTPUT_ROOT:-$ROOT_DIR/workspace/dali_unreal/Generated/PhaseOne}"
STATUS_PATH="${DALI_FISHTANK_PHASE1_STATUS_PATH:-$ROOT_DIR/workspace/runtime/phase1_idle_status.json}"
LOG_DIR="${ROOT_DIR}/.runtime/logs"
LOG_PATH="${LOG_DIR}/phase1_idle_commandlet.log"
LOCK_DIR="${DALI_FISHTANK_PHASE1_LOCK_DIR:-$ROOT_DIR/workspace/runtime/phase1_idle_run.lock}"
LOCK_HELD=0

mkdir -p "$LOG_DIR" "$(dirname "$STATUS_PATH")" "$OUTPUT_ROOT"

utc_now() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

write_status() {
  local status="$1"
  local started_at="$2"
  local completed_at="$3"
  local exit_code="$4"
  local error_text="$5"
  local run_root="$6"
  local manifest_path="$7"
  python3 - "$STATUS_PATH" "$status" "$started_at" "$completed_at" "$exit_code" "$error_text" "$run_root" "$manifest_path" \
    "$ROOT_DIR/scripts/dali_phase1_idle_run.sh" "$ENGINE_ROOT" "$UE_CMD" "$PROJECT_PATH" "$COMMANDLET_NAME" "$OUTPUT_ROOT" "$LOG_PATH" \
    "${DALI_FISHTANK_PHASE1_GRID:-}" "${DALI_FISHTANK_PHASE1_MAX_STEPS:-}" "${DALI_FISHTANK_PHASE1_BATCH_SIZE:-}" \
    "${DALI_FISHTANK_PHASE1_CHECKPOINT_EVERY:-}" "${DALI_FISHTANK_PHASE1_SEED:-}" <<'PY'
from pathlib import Path
import json
import sys

(
    status_path,
    status,
    started_at,
    completed_at,
    exit_code,
    error_text,
    run_root,
    manifest_path,
    launcher_path,
    engine_root,
    ue_cmd,
    project_path,
    commandlet_name,
    output_root,
    log_path,
    grid,
    max_steps,
    batch_size,
    checkpoint_every,
    seed,
) = sys.argv[1:]

payload = {
    "schema_version": "dali.phase1.idle-status.v1",
    "status": status,
    "started_at": started_at,
    "completed_at": completed_at,
    "exit_code": int(exit_code or "0"),
    "error": error_text,
    "launcher_path": launcher_path,
    "engine_root": engine_root,
    "ue_cmd": ue_cmd,
    "project_path": project_path,
    "commandlet_name": commandlet_name,
    "output_root": output_root,
    "run_root": run_root,
    "manifest_path": manifest_path,
    "log_path": log_path,
    "grid": grid,
    "max_steps": max_steps,
    "batch_size": batch_size,
    "checkpoint_every": checkpoint_every,
    "seed": seed,
}

target = Path(status_path)
target.parent.mkdir(parents=True, exist_ok=True)
tmp_path = target.with_suffix(target.suffix + ".tmp")
tmp_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
tmp_path.replace(target)
PY
}

latest_run_root() {
  find "$OUTPUT_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'run_*' -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | head -n 1 \
    | cut -d' ' -f2-
}

cleanup_lock() {
  if [[ "$LOCK_HELD" -eq 1 ]]; then
    rm -rf "$LOCK_DIR"
  fi
}

acquire_lock() {
  mkdir -p "$(dirname "$LOCK_DIR")"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$" >"$LOCK_DIR/pid"
    LOCK_HELD=1
    trap cleanup_lock EXIT
    return 0
  fi

  if [[ -f "$LOCK_DIR/pid" ]]; then
    local existing_pid
    existing_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      echo "[$(utc_now)] phase1_idle_run_busy existing_pid=${existing_pid}" >>"$LOG_PATH"
      exit 0
    fi
  fi

  rm -rf "$LOCK_DIR"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' "$$" >"$LOCK_DIR/pid"
    LOCK_HELD=1
    trap cleanup_lock EXIT
    return 0
  fi

  echo "[$(utc_now)] phase1_idle_run_lock_error lock_dir=${LOCK_DIR}" >>"$LOG_PATH"
  exit 1
}

fail() {
  local started_at="$1"
  local message="$2"
  local completed_at
  completed_at="$(utc_now)"
  write_status "failed" "$started_at" "$completed_at" 1 "$message" "" ""
  echo "$message" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --grid)
      export DALI_FISHTANK_PHASE1_GRID="${2:-}"
      shift 2
      ;;
    --max-steps)
      export DALI_FISHTANK_PHASE1_MAX_STEPS="${2:-}"
      shift 2
      ;;
    --batch-size)
      export DALI_FISHTANK_PHASE1_BATCH_SIZE="${2:-}"
      shift 2
      ;;
    --checkpoint-every)
      export DALI_FISHTANK_PHASE1_CHECKPOINT_EVERY="${2:-}"
      shift 2
      ;;
    --seed)
      export DALI_FISHTANK_PHASE1_SEED="${2:-}"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="${2:-}"
      mkdir -p "$OUTPUT_ROOT"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

STARTED_AT="$(utc_now)"
acquire_lock
write_status "running" "$STARTED_AT" "" 0 "" "" ""

if [[ ! -x "$UE_CMD" ]]; then
  fail "$STARTED_AT" "UE commandlet binary missing or not executable: $UE_CMD"
fi

if [[ ! -f "$PROJECT_PATH" ]]; then
  fail "$STARTED_AT" "UE project missing: $PROJECT_PATH"
fi

CMD=("$UE_CMD" "$PROJECT_PATH" "-run=${COMMANDLET_NAME}" "-unattended" "-nop4" "-NullRHI" "-OutputRoot=${OUTPUT_ROOT}")

if [[ -n "${DALI_FISHTANK_PHASE1_GRID:-}" ]]; then
  CMD+=("-Grid=${DALI_FISHTANK_PHASE1_GRID}")
fi
if [[ -n "${DALI_FISHTANK_PHASE1_MAX_STEPS:-}" ]]; then
  CMD+=("-MaxSteps=${DALI_FISHTANK_PHASE1_MAX_STEPS}")
fi
if [[ -n "${DALI_FISHTANK_PHASE1_BATCH_SIZE:-}" ]]; then
  CMD+=("-BatchSize=${DALI_FISHTANK_PHASE1_BATCH_SIZE}")
fi
if [[ -n "${DALI_FISHTANK_PHASE1_CHECKPOINT_EVERY:-}" ]]; then
  CMD+=("-CheckpointEvery=${DALI_FISHTANK_PHASE1_CHECKPOINT_EVERY}")
fi
if [[ -n "${DALI_FISHTANK_PHASE1_SEED:-}" ]]; then
  CMD+=("-Seed=${DALI_FISHTANK_PHASE1_SEED}")
fi

echo "[$(utc_now)] phase1_idle_run_start output_root=${OUTPUT_ROOT} commandlet=${COMMANDLET_NAME}" >>"$LOG_PATH"

set +e
"${CMD[@]}" >>"$LOG_PATH" 2>&1
EXIT_CODE=$?
set -e

RUN_ROOT="$(latest_run_root)"
MANIFEST_PATH=""
if [[ -n "$RUN_ROOT" && -f "$RUN_ROOT/export_manifest.json" ]]; then
  MANIFEST_PATH="$RUN_ROOT/export_manifest.json"
fi

COMPLETED_AT="$(utc_now)"
if [[ $EXIT_CODE -eq 0 ]]; then
  write_status "succeeded" "$STARTED_AT" "$COMPLETED_AT" "$EXIT_CODE" "" "$RUN_ROOT" "$MANIFEST_PATH"
  echo "[$(utc_now)] phase1_idle_run_success manifest=${MANIFEST_PATH}" >>"$LOG_PATH"
  exit 0
fi

write_status "failed" "$STARTED_AT" "$COMPLETED_AT" "$EXIT_CODE" "commandlet exited with code ${EXIT_CODE}" "$RUN_ROOT" "$MANIFEST_PATH"
echo "[$(utc_now)] phase1_idle_run_failed exit_code=${EXIT_CODE}" >>"$LOG_PATH"
exit "$EXIT_CODE"
