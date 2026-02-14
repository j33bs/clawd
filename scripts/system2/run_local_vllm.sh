#!/usr/bin/env bash
set -euo pipefail

# Operator-invoked helper to run a conservative local vLLM server on macOS.
# This script does not daemonize and does not kill existing processes.
#
# Overrides (env):
# - LOCAL_LLM_BACKEND: vllm_cpu|vllm_metal (default: vllm_cpu)
# - VLLM_VENV: path to venv to activate (optional)
# - VLLM_PYTHON: python executable (default: python3)
# - VLLM_HOST / VLLM_PORT
# - OPENCLAW_VLLM_MODEL: model name (preferred knob; consumed by OpenClaw)
# - VLLM_MODEL: model name (fallback for this script)
# - VLLM_MAX_MODEL_LEN
# - VLLM_SWAP_SPACE
# - VLLM_TARGET_DEVICE (default: cpu)
# - VLLM_CPU_KVCACHE_SPACE (default: 1)
# - OMP_NUM_THREADS (default: 4)
#
# Apple Silicon GPU/Metal path:
# - Use vllm-metal, which provides a Metal/MLX-backed vLLM build that still
#   exposes the OpenAI-compatible server (`/v1/*` endpoints).
# - Install script (summarized; see upstream README for full details):
#   - curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash
#   - (creates ~/.venv-vllm-metal by default, then installs vllm + vllm-metal wheel)
# - Run with:
#   - LOCAL_LLM_BACKEND=vllm_metal VLLM_VENV=~/.venv-vllm-metal bash scripts/system2/run_local_vllm.sh

LOCAL_LLM_BACKEND="${LOCAL_LLM_BACKEND:-vllm_cpu}"

VLLM_PYTHON="${VLLM_PYTHON:-python3}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
MODEL="${OPENCLAW_VLLM_MODEL:-${VLLM_MODEL:-Qwen/Qwen2.5-3B-Instruct}}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-1024}"
VLLM_SWAP_SPACE="${VLLM_SWAP_SPACE:-0}"

if [[ "${LOCAL_LLM_BACKEND}" == "vllm_cpu" ]]; then
  export VLLM_TARGET_DEVICE="${VLLM_TARGET_DEVICE:-cpu}"
  export VLLM_CPU_KVCACHE_SPACE="${VLLM_CPU_KVCACHE_SPACE:-1}"
  export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
elif [[ "${LOCAL_LLM_BACKEND}" == "vllm_metal" ]]; then
  # vllm-metal uses MLX/Metal; do not force cpu device.
  export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
else
  echo "ERROR: unknown LOCAL_LLM_BACKEND=${LOCAL_LLM_BACKEND} (expected: vllm_cpu|vllm_metal)" >&2
  exit 2
fi

if [[ -z "${VLLM_VENV:-}" ]]; then
  if [[ "${LOCAL_LLM_BACKEND}" == "vllm_metal" ]]; then
    VLLM_VENV="${HOME}/.venv-vllm-metal"
  elif [[ -d "${HOME}/.venv-vllm-cpu" ]]; then
    VLLM_VENV="${HOME}/.venv-vllm-cpu"
  fi
fi

if [[ -n "${VLLM_VENV:-}" ]]; then
  if [[ -f "${VLLM_VENV}/bin/activate" ]]; then
    # shellcheck disable=SC1090
    source "${VLLM_VENV}/bin/activate"
  else
    echo "ERROR: VLLM_VENV is set but no activation script found at: ${VLLM_VENV}/bin/activate" >&2
    exit 2
  fi
fi

if [[ "${LOCAL_LLM_BACKEND}" == "vllm_metal" ]]; then
  # Ensure the vllm-metal build is importable in this python environment.
  if ! "${VLLM_PYTHON}" -c "import vllm_metal" >/dev/null 2>&1; then
    echo "ERROR: vllm-metal is not importable in this Python environment." >&2
    echo "Install it (example):" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash" >&2
    echo "Then run:" >&2
    echo "  LOCAL_LLM_BACKEND=vllm_metal VLLM_VENV=~/.venv-vllm-metal bash scripts/system2/run_local_vllm.sh" >&2
    exit 2
  fi
fi

echo "=== run_local_vllm.sh ==="
echo "backend=${LOCAL_LLM_BACKEND}"
echo "host=${VLLM_HOST}"
echo "port=${VLLM_PORT}"
echo "model=${MODEL}"
if [[ "${LOCAL_LLM_BACKEND}" == "vllm_cpu" ]]; then
  echo "VLLM_TARGET_DEVICE=${VLLM_TARGET_DEVICE}"
  echo "VLLM_CPU_KVCACHE_SPACE=${VLLM_CPU_KVCACHE_SPACE}"
fi
echo "OMP_NUM_THREADS=${OMP_NUM_THREADS}"
echo "max_model_len=${VLLM_MAX_MODEL_LEN}"
echo "swap_space=${VLLM_SWAP_SPACE}"
echo ""
echo "If something is already listening on ${VLLM_HOST}:${VLLM_PORT}, stop it first:"
echo "  lsof -nP -iTCP:${VLLM_PORT} -sTCP:LISTEN"
echo ""
echo "Verify (once running):"
echo "  curl -sS --max-time 3 http://${VLLM_HOST}:${VLLM_PORT}/v1/models | head -c 200; echo"
echo "  node scripts/vllm_probe.js --json"
echo ""

exec "${VLLM_PYTHON}" -m vllm.entrypoints.openai.api_server \
  --host "${VLLM_HOST}" \
  --port "${VLLM_PORT}" \
  --model "${MODEL}" \
  --max-model-len "${VLLM_MAX_MODEL_LEN}" \
  --swap-space "${VLLM_SWAP_SPACE}" \
  --disable-log-requests
