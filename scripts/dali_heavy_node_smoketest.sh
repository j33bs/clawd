#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${DALI_HEAVY_NODE_URL:-http://127.0.0.1:${DALI_HEAVY_NODE_PORT:-18891}}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

HEALTH_JSON="$TMP_DIR/health.json"
HINT_JSON="$TMP_DIR/hint.json"

curl -fsS -m 8 "$BASE_URL/health" >"$HEALTH_JSON"
curl -fsS -m 30 -X POST "$BASE_URL/hint" \
  -H "Content-Type: application/json" \
  -d '{"problem":"Need to verify a flaky test quickly.","attempt":"I keep rerunning without isolating failure.","budget_tokens":40,"max_lines":4,"mode":"fast"}' >"$HINT_JSON"

python3 - "$HEALTH_JSON" "$HINT_JSON" <<'PY'
import json
import sys

health = json.load(open(sys.argv[1], "r", encoding="utf-8"))
hint = json.load(open(sys.argv[2], "r", encoding="utf-8"))

assert health.get("status") in {"ok", "degraded"}, health
assert isinstance(health.get("models"), dict), health

text = str(hint.get("text") or "")
lines = [line for line in text.splitlines() if line.strip()]
assert hint.get("hint_only") is True, hint
assert 2 <= len(lines) <= 4, (len(lines), text)
assert "model" in hint and "backend" in hint, hint

print("PASS dali_heavy_node_smoketest")
print(f"hint_lines={len(lines)}")
PY
