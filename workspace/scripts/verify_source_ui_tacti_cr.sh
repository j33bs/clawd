#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="$REPO_ROOT/workspace/source-ui/app.py"
HTML_PATH="$REPO_ROOT/workspace/source-ui/index.html"
CSS_PATH="$REPO_ROOT/workspace/source-ui/css/styles.css"
PORT="${1:-19998}"
HOST="127.0.0.1"
LOG_FILE="$(mktemp -t source-ui-verify.XXXXXX.log)"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

python3 "$APP_PATH" --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!
sleep 1

if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
  echo "FAIL: Source UI failed to start"
  cat "$LOG_FILE"
  exit 1
fi

check_contract() {
  local endpoint="$1"
  local method="${2:-GET}"
  local body="${3:-}"
  local raw
  if [[ "$method" == "GET" ]]; then
    raw="$(curl -sS "http://$HOST:$PORT$endpoint")"
  else
    raw="$(curl -sS -X "$method" -H 'Content-Type: application/json' -d "$body" "http://$HOST:$PORT$endpoint")"
  fi

  python3 -c 'import json,sys
endpoint=sys.argv[1]
try:
    payload=json.load(sys.stdin)
except Exception as exc:
    raise SystemExit(f"FAIL: {endpoint} not valid JSON: {exc}")
required={"ok","ts","data","error"}
if not required.issubset(payload.keys()):
    raise SystemExit(f"FAIL: {endpoint} missing contract keys")
print("PASS: %s ok=%s" % (endpoint, payload.get("ok")))' "$endpoint" <<<"$raw"
}

check_contract "/api/status"
check_contract "/api/tacti/dream"
check_contract "/api/hivemind/stigmergy"
check_contract "/api/tacti/immune"
check_contract "/api/tacti/arousal"
check_contract "/api/hivemind/trails"
check_contract "/api/hivemind/peer-graph"
check_contract "/api/skills"
check_contract "/api/tacti/dream/run" "POST" "{}"
check_contract "/api/hivemind/stigmergy/query" "POST" '{"query":"main"}'
check_contract "/api/hivemind/trails/trigger" "POST" '{"text":"verify trigger","tags":["source-ui"]}'

# HTML/CSS structure checks (non-brittle).
rg -q 'id="tacti-status-strip"' "$HTML_PATH"
rg -q 'id="quick-actions-strip"' "$HTML_PATH"
rg -q 'id="panel-dream"' "$HTML_PATH"
rg -q 'id="panel-stigmergy"' "$HTML_PATH"
rg -q 'id="panel-immune"' "$HTML_PATH"
rg -q 'id="panel-arousal"' "$HTML_PATH"
rg -q 'id="panel-trails"' "$HTML_PATH"
rg -q 'id="panel-peer-graph"' "$HTML_PATH"
rg -q 'id="panel-skills"' "$HTML_PATH"
rg -q -- '--cat-arousal' "$CSS_PATH"
rg -q -- '--cat-temporality' "$CSS_PATH"
rg -q -- '--cat-cross-timescale' "$CSS_PATH"
rg -q -- '--cat-malleability' "$CSS_PATH"
rg -q -- '--cat-agency' "$CSS_PATH"

echo "PASS: source-ui TACTI(C)-R verification complete"
