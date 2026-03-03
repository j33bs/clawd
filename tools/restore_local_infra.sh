#!/usr/bin/env bash
set -euo pipefail

if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$REPO_ROOT"

DRY_RUN="${RESTORE_DRY_RUN:-0}"
UID_NUM="$(id -u)"
PINNED_COMMIT="511a4db716dfe12da62036bbf149a481a95fc76d"
FORCE_RESTORE_PATHS="${RESTORE_FORCE_RESTORE_PATHS:-}"

qmd_ok=0
ain_ok=0

step() {
  echo
  echo "== $1 =="
}

run_or_dry() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY_RUN] $*"
    return 0
  fi
  "$@"
}

path_forced_restore() {
  local path="$1"
  if [ -z "$FORCE_RESTORE_PATHS" ]; then
    return 1
  fi
  [[ ",$FORCE_RESTORE_PATHS," == *",$path,"* ]]
}

restore_from_commit() {
  local commit="$1"
  local path="$2"

  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY_RUN] would restore $path from $commit"
    return 0
  fi

  if ! command -v git >/dev/null 2>&1; then
    echo "WARN: git unavailable; cannot restore $path from $commit"
    return 0
  fi
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "WARN: not a git repo; cannot restore $path from $commit"
    return 0
  fi
  if ! git cat-file -e "$commit^{commit}" >/dev/null 2>&1; then
    echo "WARN: commit object $commit not present locally; cannot restore $path"
    return 0
  fi
  if ! git cat-file -e "$commit:$path" >/dev/null 2>&1; then
    echo "WARN: $path not found in commit $commit"
    return 0
  fi
  if git restore --source="$commit" -- "$path" >/dev/null 2>&1; then
    echo "OK: restored $path from $commit"
  else
    echo "WARN: failed to restore $path from $commit"
  fi
}

ensure_asset_from_pinned_commit() {
  local path="$1"
  if [ -f "$path" ] && ! path_forced_restore "$path"; then
    return 0
  fi
  if path_forced_restore "$path"; then
    echo "INFO: forced restore requested for $path"
  else
    echo "INFO: missing asset $path"
  fi
  restore_from_commit "$PINNED_COMMIT" "$path"
}

http_reachable() {
  local url="$1"
  local code
  code="$(curl -sS --max-time 2 -o /dev/null -w "%{http_code}" "$url" || true)"
  [ -n "$code" ] && [ "$code" != "000" ]
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-10}"
  local delay_s="${3:-0.5}"
  local i=1
  while [ "$i" -le "$attempts" ]; do
    if http_reachable "$url"; then
      return 0
    fi
    sleep "$delay_s"
    i=$((i + 1))
  done
  return 1
}

service_reachable() {
  local url="$1"
  if [ "$DRY_RUN" = "1" ]; then
    http_reachable "$url"
  else
    wait_for_http "$url"
  fi
}

step "Restore Local Infra (dry_run=$DRY_RUN)"

step "Phase 1: Runtime Directories"
run_or_dry mkdir -p workspace/runtime workspace/runtime/logs || true
if [ "$DRY_RUN" = "1" ]; then
  echo "INFO: directory creation skipped in dry-run"
else
  echo "OK: ensured workspace/runtime and workspace/runtime/logs"
fi

step "Phase 2: QMD MCP (8181)"
ensure_asset_from_pinned_commit "tools/qmd_mcp_start_ipv4.sh"
if [ -f tools/qmd_mcp_start_ipv4.sh ] && [ ! -x tools/qmd_mcp_start_ipv4.sh ]; then
  run_or_dry chmod +x tools/qmd_mcp_start_ipv4.sh || true
fi

if lsof -nP -iTCP:8181 -sTCP:LISTEN 2>/dev/null | grep -q "127.0.0.1:8181 (LISTEN)"; then
  echo "OK: QMD listener already on 127.0.0.1:8181"
else
  echo "INFO: QMD listener missing on 127.0.0.1:8181"
  if [ -x tools/qmd_mcp_start_ipv4.sh ]; then
    run_or_dry tools/qmd_mcp_start_ipv4.sh || echo "WARN: qmd_mcp_start_ipv4.sh failed"
  else
    echo "WARN: tools/qmd_mcp_start_ipv4.sh not found or not executable"
  fi
fi

if service_reachable "http://127.0.0.1:8181/mcp"; then
  echo "OK: QMD MCP reachable at http://127.0.0.1:8181/mcp"
  qmd_ok=1
else
  echo "FAIL: QMD MCP unreachable at http://127.0.0.1:8181/mcp"
fi

step "Phase 3: AIN (18990)"
ensure_asset_from_pinned_commit "tools/install_launchagent_ain.sh"
if [ -f tools/install_launchagent_ain.sh ] && [ ! -x tools/install_launchagent_ain.sh ]; then
  run_or_dry chmod +x tools/install_launchagent_ain.sh || true
fi
ensure_asset_from_pinned_commit "workspace/launchd/ai.openclaw.ain.plist"
ensure_asset_from_pinned_commit "workspace/source-ui/run-source-ui.sh"

if launchctl list 2>/dev/null | grep -q "ai.openclaw.ain"; then
  echo "OK: launchctl label ai.openclaw.ain present"
  run_or_dry launchctl kickstart -k "gui/$UID_NUM/ai.openclaw.ain" || echo "WARN: launchctl kickstart failed"
else
  echo "INFO: launchctl label ai.openclaw.ain not present"
  if [ -x tools/install_launchagent_ain.sh ]; then
    run_or_dry tools/install_launchagent_ain.sh || echo "WARN: install_launchagent_ain.sh failed"
  else
    echo "WARN: tools/install_launchagent_ain.sh not found or not executable"
  fi
fi

if service_reachable "http://127.0.0.1:18990/"; then
  echo "OK: AIN reachable at http://127.0.0.1:18990/"
  ain_ok=1
else
  echo "FAIL: AIN unreachable at http://127.0.0.1:18990/"
fi

step "Phase 4: Final Status"
printf "%-10s %-8s %-5s\n" "SERVICE" "STATUS" "PORT"
printf "%-10s %-8s %-5s\n" "QMD MCP" "$([ "$qmd_ok" -eq 1 ] && echo OK || echo FAIL)" "8181"
printf "%-10s %-8s %-5s\n" "AIN" "$([ "$ain_ok" -eq 1 ] && echo OK || echo FAIL)" "18990"

if [ "$qmd_ok" -eq 1 ] && [ "$ain_ok" -eq 1 ]; then
  exit 0
fi
if [ "$qmd_ok" -eq 1 ] || [ "$ain_ok" -eq 1 ]; then
  exit 1
fi
exit 2
