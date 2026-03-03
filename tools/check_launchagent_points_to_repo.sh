#!/usr/bin/env bash
set -euo pipefail

PLIST="${1:-$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXPECTED_REPO="${OPENCLAW_EXPECTED_REPO:-${OPENCLAW_HOME:-$DEFAULT_REPO}}"
EXPECTED_WRAPPER="${OPENCLAW_EXPECTED_WRAPPER:-${EXPECTED_REPO}/scripts/run_openclaw_gateway_repo.sh}"

if [[ ! -f "$PLIST" ]]; then
  echo "FAIL: plist not found: $PLIST" >&2
  exit 1
fi

plist_json="$(plutil -p "$PLIST" 2>/dev/null || true)"
if [[ -z "$plist_json" ]]; then
  echo "FAIL: unable to parse plist: $PLIST" >&2
  exit 1
fi

if ! grep -Fq "$EXPECTED_WRAPPER" <<<"$plist_json"; then
  echo "FAIL: ProgramArguments does not reference expected wrapper: $EXPECTED_WRAPPER" >&2
  exit 1
fi
if ! grep -Fq "$EXPECTED_REPO" <<<"$plist_json"; then
  echo "FAIL: plist does not reference expected repo root: $EXPECTED_REPO" >&2
  exit 1
fi

echo "PASS: launchagent points to repo wrapper (${EXPECTED_WRAPPER})"
