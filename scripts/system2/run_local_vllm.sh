#!/usr/bin/env bash
set -euo pipefail

# Operator-invoked helper to run a conservative local vLLM server on macOS.
# This script does not daemonize and does not kill existing processes.
#
# Overrides (env):
# - VLLM_VENV: path to venv to activate (optional)
# - VLLM_PYTHON: python executable (default: python3)
# - VLLM_HOST / VLLM_PORT
# - VLLM_MODEL
# - VLLM_MAX_MODEL_LEN
# - VLLM_SWAP_SPACE
# - VLLM_TARGET_DEVICE (default: cpu)
# - VLLM_CPU_KVCACHE_SPACE (default: 1)
# - OMP_NUM_THREADS (default: 4)

VLLM_PYTHON="${VLLM_PYTHON:-python3}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
VLLM_MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-3B-Instruct}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-1024}"
VLLM_SWAP_SPACE="${VLLM_SWAP_SPACE:-0}"

export VLLM_TARGET_DEVICE="${VLLM_TARGET_DEVICE:-cpu}"
export VLLM_CPU_KVCACHE_SPACE="${VLLM_CPU_KVCACHE_SPACE:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"

if [[ -n "${VLLM_VENV:-}" ]]; then
  if [[ -f "${VLLM_VENV}/bin/activate" ]]; then
    # shellcheck disable=SC1090
    source "${VLLM_VENV}/bin/activate"
  else
    echo "ERROR: VLLM_VENV is set but no activation script found at: ${VLLM_VENV}/bin/activate" >&2
    exit 2
  fi
fi

echo "=== run_local_vllm.sh ==="
echo "host=${VLLM_HOST}"
echo "port=${VLLM_PORT}"
echo "model=${VLLM_MODEL}"
echo "VLLM_TARGET_DEVICE=${VLLM_TARGET_DEVICE}"
echo "VLLM_CPU_KVCACHE_SPACE=${VLLM_CPU_KVCACHE_SPACE}"
echo "OMP_NUM_THREADS=${OMP_NUM_THREADS}"
echo "max_model_len=${VLLM_MAX_MODEL_LEN}"
echo "swap_space=${VLLM_SWAP_SPACE}"
echo ""
echo "If something is already listening on ${VLLM_HOST}:${VLLM_PORT}, stop it first:"
echo "  lsof -nP -iTCP:${VLLM_PORT} -sTCP:LISTEN"
echo ""
echo "Verify once running:"
echo "  curl -sS --max-time 3 http://${VLLM_HOST}:${VLLM_PORT}/v1/models | head -c 200; echo"
echo "  node scripts/vllm_probe.js"
echo ""

exec "${VLLM_PYTHON}" -m vllm.entrypoints.openai.api_server \
  --host "${VLLM_HOST}" \
  --port "${VLLM_PORT}" \
  --model "${VLLM_MODEL}" \
  --max-model-len "${VLLM_MAX_MODEL_LEN}" \
  --swap-space "${VLLM_SWAP_SPACE}" \
  --disable-log-requests

