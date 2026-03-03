#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VLLM_PYTHON="${OPENCLAW_VLLM_PYTHON:-$ROOT_DIR/.venv-vllm/bin/python3.12}"
VLLM_ENTRYPOINT="${OPENCLAW_VLLM_ENTRYPOINT:-$ROOT_DIR/.venv-vllm/bin/vllm}"
MODEL_PATH="${OPENCLAW_VLLM_ASSISTANT_MODEL_PATH:-/opt/models/qwen2_5_14b_instruct_awq}"
SERVED_MODEL_NAME="${OPENCLAW_VLLM_ASSISTANT_SERVED_MODEL_NAME:-local-assistant}"
VLLM_HOST="${OPENCLAW_VLLM_ASSISTANT_HOST:-127.0.0.1}"
VLLM_PORT="${OPENCLAW_VLLM_ASSISTANT_PORT:-8001}"
VLLM_GPU_UTILIZATION="${OPENCLAW_VLLM_ASSISTANT_GPU_MEMORY_UTILIZATION:-0.85}"
VLLM_MAX_MODEL_LEN="${OPENCLAW_VLLM_ASSISTANT_MAX_MODEL_LEN:-16384}"
VLLM_MAX_NUM_SEQS="${OPENCLAW_VLLM_ASSISTANT_MAX_NUM_SEQS:-8}"
ASSISTANT_LOG_PATH="${OPENCLAW_VLLM_ASSISTANT_LOG_PATH:-$HOME/.local/state/openclaw/vllm-assistant.log}"

mkdir -p "$(dirname "$ASSISTANT_LOG_PATH")"

set +e
"$ROOT_DIR/scripts/ensure_port_free.sh" "$VLLM_PORT"
PORT_GUARD_EC=$?
set -e
if [[ $PORT_GUARD_EC -ne 0 ]]; then
  echo "VLLM_ASSISTANT_PREFLIGHT_FAILED reason=port_guard_failed port=$VLLM_PORT exit_code=$PORT_GUARD_EC" >&2
  exit "$PORT_GUARD_EC"
fi

if [[ ! -x "$VLLM_PYTHON" ]]; then
  echo "VLLM_ASSISTANT_PREFLIGHT_FAILED reason=python_missing path=$VLLM_PYTHON" >&2
  exit 42
fi

if [[ ! -x "$VLLM_ENTRYPOINT" ]]; then
  echo "VLLM_ASSISTANT_PREFLIGHT_FAILED reason=entrypoint_missing path=$VLLM_ENTRYPOINT" >&2
  exit 42
fi

if [[ ! -d "$MODEL_PATH" && ! -f "$MODEL_PATH" ]]; then
  echo "VLLM_ASSISTANT_PREFLIGHT_FAILED reason=model_missing model=$MODEL_PATH" >&2
  exit 42
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  set +e
  GPU_MEM_RAW="$(nvidia-smi --query-gpu=memory.total,memory.free --format=csv,noheader,nounits 2>/dev/null | head -n 1)"
  GPU_MEM_EC=$?
  set -e
  if [[ $GPU_MEM_EC -eq 0 && -n "$GPU_MEM_RAW" ]]; then
    GPU_TOTAL_MB="$(printf '%s' "$GPU_MEM_RAW" | awk -F',' '{gsub(/ /, "", $1); print $1}')"
    GPU_FREE_MB="$(printf '%s' "$GPU_MEM_RAW" | awk -F',' '{gsub(/ /, "", $2); print $2}')"
    REQUIRED_FREE_MB="$("$VLLM_PYTHON" - <<'PY' "$GPU_TOTAL_MB" "$VLLM_GPU_UTILIZATION"
import math
import sys
total = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
util = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85
print(max(0, math.ceil(total * util)))
PY
)"
    if [[ "$GPU_FREE_MB" =~ ^[0-9]+$ ]] && [[ "$REQUIRED_FREE_MB" =~ ^[0-9]+$ ]] && (( GPU_FREE_MB < REQUIRED_FREE_MB )); then
      echo "VLLM_ASSISTANT_START_BLOCKED reason=GPU_MEM_LOW free_mb=$GPU_FREE_MB required_mb=$REQUIRED_FREE_MB gpu_util=$VLLM_GPU_UTILIZATION" >&2
      exit 42
    fi
  fi
fi

echo "=== vllm_launch_assistant.sh ==="
echo "host=$VLLM_HOST port=$VLLM_PORT model=$MODEL_PATH served_model=$SERVED_MODEL_NAME"
echo "python=$VLLM_PYTHON entrypoint=$VLLM_ENTRYPOINT gpu_util=$VLLM_GPU_UTILIZATION max_model_len=$VLLM_MAX_MODEL_LEN max_num_seqs=$VLLM_MAX_NUM_SEQS"

exec "$VLLM_PYTHON" "$VLLM_ENTRYPOINT" serve "$MODEL_PATH" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --host "$VLLM_HOST" \
  --port "$VLLM_PORT" \
  --quantization awq \
  --dtype auto \
  --gpu-memory-utilization "$VLLM_GPU_UTILIZATION" \
  --max-model-len "$VLLM_MAX_MODEL_LEN" \
  --max-num-seqs "$VLLM_MAX_NUM_SEQS" \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --uvicorn-log-level warning
