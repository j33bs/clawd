#!/usr/bin/env bash
set -euo pipefail

SOURCE_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SOURCE_PATH}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

RUNTIME_DIR="$REPO_ROOT/workspace/runtime"
VERIFY_DIR="$RUNTIME_DIR/cel_verify"
OUTPUT_DIR="$RUNTIME_DIR/codex_outputs"
METRICS_FILE="$RUNTIME_DIR/token_metrics.jsonl"
PREPARED_FILE="$RUNTIME_DIR/codex_prepared_prompt.json"
SESSIONS_LOG="$RUNTIME_DIR/codex_sessions.log"

mkdir -p "$RUNTIME_DIR" "$VERIFY_DIR" "$OUTPUT_DIR"

rm -f "$PREPARED_FILE" "$SESSIONS_LOG" "$METRICS_FILE"
rm -rf "$OUTPUT_DIR/cel-verify-session"

PROMPT_FILE="$VERIFY_DIR/codex_prompt_verify.md"
cat > "$PROMPT_FILE" <<'MD'
GOAL
Run CEL verification in dry-run mode.

INPUTS
- `workspace/scripts/message_handler.py`
- `tools/codex_spawn_session.py`

OUTPUTS
- Verification JSON outputs

CONSTRAINTS
- Keep compatibility with existing gateway contracts.

SUCCESS_CRITERIA
- All verification checks pass.
MD

python3 tools/codex_prepare_prompt.py "$PROMPT_FILE" --output "$PREPARED_FILE" > "$VERIFY_DIR/prepare.out.json"

test -f "$PREPARED_FILE"

python3 tools/codex_spawn_session.py \
  --prepared "$PREPARED_FILE" \
  --dry-run \
  --context-json '{"verification":true,"phase":"spawn"}' \
  > "$VERIFY_DIR/spawn.out.json"

test -f "$SESSIONS_LOG"

STATUS_FIXTURE="$VERIFY_DIR/status_fixture.json"
cat > "$STATUS_FIXTURE" <<'JSON'
{
  "sessionId": "cel-verify-session",
  "usage": {
    "prompt_tokens": 120,
    "completion_tokens": 80,
    "total_tokens": 200
  }
}
JSON

python3 tools/codex_token_watchdog.py \
  --session-id cel-verify-session \
  --status-file "$STATUS_FIXTURE" \
  --iterations 1 \
  --metrics-path "$METRICS_FILE" \
  > "$VERIFY_DIR/watchdog.out.json"

test -f "$METRICS_FILE"

HISTORY_FIXTURE="$VERIFY_DIR/history_fixture.json"
cat > "$HISTORY_FIXTURE" <<'JSON'
{
  "sessionId": "cel-verify-session",
  "history": [
    {"role": "user", "content": "run verification"},
    {"role": "assistant", "content": "verification complete"}
  ]
}
JSON

python3 tools/codex_finalize_session.py \
  --session-id cel-verify-session \
  --history-file "$HISTORY_FIXTURE" \
  --status-file "$STATUS_FIXTURE" \
  --skip-terminate \
  --output-root "$OUTPUT_DIR" \
  > "$VERIFY_DIR/finalize.out.json"

test -f "$OUTPUT_DIR/cel-verify-session/history.json"
test -f "$OUTPUT_DIR/cel-verify-session/outputs.txt"
test -f "$OUTPUT_DIR/cel-verify-session/summary.json"

# No contract drift: ensure CEL changes did not mutate canonical contract surfaces.
CONTRACT_PATHS=(
  "workspace/policy/llm_policy.json"
  "scripts/system2_http_edge.js"
  "workspace/runtime_hardening/src/http_ingress_contract_signal.mjs"
)
if git diff --quiet -- "${CONTRACT_PATHS[@]}"; then
  echo "PASS: no contract drift on canonical surfaces" > "$VERIFY_DIR/contract_invariants.out.txt"
else
  echo "FAIL: contract drift detected on canonical surfaces" > "$VERIFY_DIR/contract_invariants.out.txt"
  git diff -- "${CONTRACT_PATHS[@]}" >> "$VERIFY_DIR/contract_invariants.out.txt"
  exit 1
fi

OPENCLAW_WRAPPER_DRYRUN=1 bash scripts/run_openclaw_gateway_repo.sh > "$VERIFY_DIR/gateway_boot.out.txt" 2>&1

if [[ "${CEL_SMOKE:-0}" == "1" ]]; then
  bash tools/cel_smoke_test.sh | tee "$VERIFY_DIR/smoke.out.txt"
fi

echo "verify_codex_efficiency_layer: PASS"
