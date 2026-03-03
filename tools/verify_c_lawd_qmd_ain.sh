#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

FAIL=0
UID_NUM="$(id -u)"

check_http_reachable() {
  local url="$1"
  local name="$2"
  local code
  code="$(curl -sS --max-time 2 -o /dev/null -w "%{http_code}" "$url" || true)"
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    echo "PASS: $name reachable ($url, http_code=$code)"
  else
    echo "FAIL: $name not reachable ($url)"
    FAIL=1
  fi
}

if bash -n workspace/source-ui/run-source-ui.sh; then
  echo "PASS: bash -n workspace/source-ui/run-source-ui.sh"
else
  echo "FAIL: bash -n workspace/source-ui/run-source-ui.sh"
  FAIL=1
fi

check_http_reachable "http://127.0.0.1:8181/mcp" "qmd-mcp"
check_http_reachable "http://127.0.0.1:18990/" "ain-source-ui"

if launchctl list | grep -q "ai.openclaw.ain"; then
  echo "PASS: launchctl label ai.openclaw.ain present"
  launchctl print "gui/$UID_NUM/ai.openclaw.ain" >/dev/null 2>&1 || true
else
  echo "INFO: launchctl label ai.openclaw.ain not installed in current user session"
fi

if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
