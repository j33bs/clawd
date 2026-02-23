#!/usr/bin/env bash
set -euo pipefail

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
  REASON="$($VLLM_PYTHON - <<'PY' "$VRAM_JSON"
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else '{}'
try:
    obj = json.loads(raw)
except Exception:
    obj = {}
print(str(obj.get('reason') or 'UNKNOWN'))
PY
)"
  MSG="VRAM_GUARD_BLOCKED: reason=${REASON} details=${VRAM_JSON}"
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
