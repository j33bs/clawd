#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$HOME/src/clawd}"
RUNS="${RUNS:-25}"
LOG_DIR="${LOG_DIR:-/tmp/dash_repro}"

mkdir -p "$LOG_DIR"

run_case() {
  local mode="$1"
  local i="$2"
  local log_path="$LOG_DIR/${mode}_$(printf '%02d' "$i").log"
  local ec=0

  if [[ "$mode" == "unset" ]]; then
    set +e
    env -i HOME="$HOME" PATH="$PATH" OPENCLAW_QUIESCE=1 OPENCLAW_HARDENING_DEBUG=1 NODE_ENV=development \
      bash -lc "cd '$ROOT' && timeout 2s openclaw dashboard --no-open" >"$log_path" 2>&1
    ec=$?
    set -e
  else
    set +e
    env -i HOME="$HOME" PATH="$PATH" OPENCLAW_QUIESCE=1 OPENCLAW_HARDENING_DEBUG=1 NODE_ENV=development OPENCLAW_PROVIDER_ALLOWLIST=local_vllm \
      bash -lc "cd '$ROOT' && timeout 2s openclaw dashboard --no-open" >"$log_path" 2>&1
    ec=$?
    set -e
  fi

  if rg -q "ANTHROPIC_API_KEY: required non-empty value is missing" "$log_path"; then
    echo "FAIL mode=$mode iteration=$i log=$log_path"
    rg -n "hardening_debug" "$log_path" || true
    return 1
  fi

  if rg -q "Dashboard URL:" "$log_path"; then
    return 0
  fi

  if [[ "$ec" -eq 124 ]] && rg -q "hardening_debug" "$log_path"; then
    # timed out before URL print is possible; still treat as failure for deterministic startup contract
    echo "FAIL mode=$mode iteration=$i log=$log_path timeout_before_dashboard_url"
    rg -n "hardening_debug" "$log_path" || true
    return 1
  fi

  echo "FAIL mode=$mode iteration=$i log=$log_path exit=$ec missing_dashboard_url"
  rg -n "hardening_debug" "$log_path" || true
  return 1
}

for i in $(seq 1 "$RUNS"); do
  run_case "unset" "$i"
  run_case "local" "$i"
  echo "PASS iteration=$i"
done

echo "PASS all_runs=$RUNS modes=2 logs=$LOG_DIR"
