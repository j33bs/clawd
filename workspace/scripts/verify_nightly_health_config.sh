#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT_DIR/workspace/scripts/nightly_build.sh"

if ! command -v openclaw >/dev/null 2>&1; then
    echo "SKIP: openclaw not found on PATH"
    exit 0
fi

echo "[verify] valid-config path"
VALID_OUT="$(mktemp)"
if ! CLAWD_DIR="$ROOT_DIR" bash "$SCRIPT" health >"$VALID_OUT" 2>&1; then
    echo "FAIL: expected health to succeed with valid config"
    sed -n '1,120p' "$VALID_OUT"
    rm -f "$VALID_OUT"
    exit 1
fi
grep -q "OpenClaw config preflight: OK" "$VALID_OUT"

echo "[verify] invalid-config path"
TMPHOME="$(mktemp -d)"
INVALID_OUT="$(mktemp)"
mkdir -p "$TMPHOME/.openclaw"
cat > "$TMPHOME/.openclaw/openclaw.json" <<'JSON'
{
  "plugins": {
    "load": {
      "paths": ["/nope/missing_plugin.js"]
    },
    "entries": {
      "openclaw_secrets_plugin": {
        "enabled": true
      }
    }
  }
}
JSON

set +e
HOME="$TMPHOME" \
USERPROFILE="$TMPHOME" \
CLAWD_DIR="$ROOT_DIR" \
OPENCLAW_CONFIG_PATH="$TMPHOME/.openclaw/openclaw.json" \
bash "$SCRIPT" health >"$INVALID_OUT" 2>&1
INVALID_EXIT=$?
set -e

if [ "$INVALID_EXIT" -eq 0 ]; then
    echo "FAIL: expected health to fail with invalid config"
    sed -n '1,160p' "$INVALID_OUT"
    rm -rf "$TMPHOME"
    rm -f "$VALID_OUT" "$INVALID_OUT"
    exit 1
fi

grep -q "OpenClaw config invalid (likely ~/.openclaw/openclaw.json). Run: openclaw doctor --fix" "$INVALID_OUT"
grep -q "OpenClaw doctor diagnostics (last 20 lines):" "$INVALID_OUT"

echo "PASS: nightly health config preflight behaves as expected"
rm -rf "$TMPHOME"
rm -f "$VALID_OUT" "$INVALID_OUT"
