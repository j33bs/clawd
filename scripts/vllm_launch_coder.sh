#!/usr/bin/env bash
set -euo pipefail

SCRIPT_SELF="$(readlink -f "$0" 2>/dev/null || printf '%s' "$0")"
if [[ ! -x "$SCRIPT_SELF" ]]; then
  echo "VLLM_CODER_EXEC_PERM_FIX applied chmod +x $SCRIPT_SELF" >&2
  chmod +x "$SCRIPT_SELF"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VLLM_PYTHON="${VLLM_PYTHON:-python3}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_CODER_PORT:-8002}"
MODEL="${OPENCLAW_VLLM_CODER_MODEL:-${VLLM_CODER_MODEL:-local-coder}}"
VLLM_MAX_MODEL_LEN="${VLLM_CODER_MAX_MODEL_LEN:-16384}"
VLLM_SWAP_SPACE="${VLLM_CODER_SWAP_SPACE:-0}"
CODER_LOG_PATH="${OPENCLAW_VLLM_CODER_LOG_PATH:-$HOME/.local/state/openclaw/vllm-coder.log}"

mkdir -p "$(dirname "$CODER_LOG_PATH")"

set +e
VRAM_JSON="$($VLLM_PYTHON "$ROOT_DIR/scripts/vram_guard.py" --json 2>&1)"
VRAM_RC=$?
set -e
if [[ $VRAM_RC -ne 0 ]]; then
  PARSED="$($VLLM_PYTHON - <<'PY' "$VRAM_JSON" "${VLLM_CODER_MIN_FREE_VRAM_MB:-7000}"
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else '{}'
threshold = sys.argv[2] if len(sys.argv) > 2 else '7000'
try:
    obj = json.loads(raw)
except Exception:
    obj = {}
reason = str(obj.get('reason') or 'UNKNOWN')
free_mb = obj.get('max_free_vram_mb')
if free_mb is None:
    free_mb = "na"
print(f"{reason}|{free_mb}|{threshold}")
PY
)"
  REASON="${PARSED%%|*}"
  REST="${PARSED#*|}"
  FREE_MB="${REST%%|*}"
  MIN_FREE_MB="${REST##*|}"
  MARKER="VLLM_CODER_START_BLOCKED reason=${REASON} free_mb=${FREE_MB} min_free_mb=${MIN_FREE_MB}"
  MSG="${MARKER} details=${VRAM_JSON}"
  echo "$MSG" >&2
  printf '%s\n' "$MSG" >> "$CODER_LOG_PATH" || true
  exit 42
fi

echo "=== vllm_launch_coder.sh ==="
echo "host=${VLLM_HOST}"
echo "port=${VLLM_PORT}"
echo "model=${MODEL}"
echo "max_model_len=${VLLM_MAX_MODEL_LEN}"
echo "swap_space=${VLLM_SWAP_SPACE}"
echo "vram_guard=${VRAM_JSON}"

exec "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
  --host "$VLLM_HOST" \
  --port "$VLLM_PORT" \
  --model "$MODEL" \
  --max-model-len "$VLLM_MAX_MODEL_LEN" \
  --swap-space "$VLLM_SWAP_SPACE" \
  --disable-log-requests
