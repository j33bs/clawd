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
# - VLLM_DTYPE: override dtype (metal default: float16; cpu default: unset)
# - VLLM_TARGET_DEVICE (default: cpu)
# - VLLM_CPU_KVCACHE_SPACE (default: 1)
# - OMP_NUM_THREADS (default: 4)
#
# Apple Silicon GPU/Metal path (supported operator flow):
# - Use the official vllm-metal installer to create a coherent venv. This avoids
#   pip dependency tug-of-war (e.g. vLLM pins transformers<5 while some MLX
#   ecosystem packages pull transformers>=5).
# - Install script (summarized; see upstream README for the authoritative flow):
#     curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash
#   This creates ~/.venv-vllm-metal by default.
# - Run with:
#   - LOCAL_LLM_BACKEND=vllm_metal VLLM_VENV=~/.venv-vllm-metal bash scripts/system2/run_local_vllm.sh

LOCAL_LLM_BACKEND="${LOCAL_LLM_BACKEND:-vllm_cpu}"

VLLM_PYTHON="${VLLM_PYTHON:-python3}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8000}"
MODEL="${OPENCLAW_VLLM_MODEL:-${VLLM_MODEL:-Qwen/Qwen2.5-3B-Instruct}}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-1024}"
VLLM_SWAP_SPACE="${VLLM_SWAP_SPACE:-0}"
VLLM_DTYPE="${VLLM_DTYPE:-}"

if [[ "${LOCAL_LLM_BACKEND}" == "vllm_cpu" ]]; then
  export VLLM_TARGET_DEVICE="${VLLM_TARGET_DEVICE:-cpu}"
  export VLLM_CPU_KVCACHE_SPACE="${VLLM_CPU_KVCACHE_SPACE:-1}"
  export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
elif [[ "${LOCAL_LLM_BACKEND}" == "vllm_metal" ]]; then
  # vllm-metal uses MLX/Metal; do not force cpu device.
  export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
  # Metal/MPS is more reliable with float16 than bfloat16 on many configs.
  VLLM_DTYPE="${VLLM_DTYPE:-float16}"
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

if [[ "${LOCAL_LLM_BACKEND}" == "vllm_metal" ]]; then
  if [[ -z "${VLLM_VENV:-}" ]]; then
    echo "ERROR: VLLM_VENV is required for LOCAL_LLM_BACKEND=vllm_metal (expected default: ~/.venv-vllm-metal)" >&2
    exit 2
  fi
  if [[ ! -f "${VLLM_VENV}/bin/activate" ]]; then
    echo "ERROR: vllm-metal venv missing or incomplete: ${VLLM_VENV}/bin/activate" >&2
    echo "Install the Metal backend via the official installer:" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash" >&2
    exit 2
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
  # Always use the venv python for metal to avoid accidentally launching with system python.
  VLLM_PYTHON="${VLLM_VENV}/bin/python3"

  # Sanity check: vLLM should import cleanly in this venv.
  if ! "${VLLM_PYTHON}" -c "import vllm" >/dev/null 2>&1; then
    echo "ERROR: vLLM is not importable in this venv (incomplete install)." >&2
    echo "Reinstall via the official installer:" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash" >&2
    exit 2
  fi

  # Ensure the vllm-metal build is importable in this python environment.
  if ! "${VLLM_PYTHON}" -c "import vllm_metal" >/dev/null 2>&1; then
    echo "ERROR: vllm-metal is not importable in this Python environment." >&2
    echo "Install it (example):" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash" >&2
    echo "Then run:" >&2
    echo "  LOCAL_LLM_BACKEND=vllm_metal VLLM_VENV=~/.venv-vllm-metal bash scripts/system2/run_local_vllm.sh" >&2
    exit 2
  fi

  # vllm-metal runtime currently imports MambaCache from mlx_lm. If this fails,
  # the environment is inconsistent (often from mixing MLX ecosystem packages).
  if ! "${VLLM_PYTHON}" -c "from mlx_lm.models.cache import MambaCache" >/dev/null 2>&1; then
    echo "ERROR: mlx-lm in this venv is missing MambaCache (vllm-metal runtime incompatibility)." >&2
    echo "Supported operator path:" >&2
    echo "  1) Reinstall vllm-metal via the official installer into a fresh venv." >&2
    echo "  2) Avoid mixing mlx-lm/mlx-vlm versions from other projects into this venv." >&2
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
if [[ -n "${VLLM_DTYPE}" ]]; then
  echo "dtype=${VLLM_DTYPE}"
fi
echo "OMP_NUM_THREADS=${OMP_NUM_THREADS}"
echo "max_model_len=${VLLM_MAX_MODEL_LEN}"
echo "swap_space=${VLLM_SWAP_SPACE}"
echo ""
echo "If something is already listening on ${VLLM_HOST}:${VLLM_PORT}, stop it first:"
echo "  lsof -nP -iTCP:${VLLM_PORT} -sTCP:LISTEN"
echo ""
echo "Verify (in another terminal, once running):"
echo "  curl -sS --max-time 3 http://${VLLM_HOST}:${VLLM_PORT}/v1/models | head -c 200; echo"
echo "  node scripts/vllm_probe.js --json"
echo ""

dtype_args=()
if [[ -n "${VLLM_DTYPE}" ]]; then
  dtype_args=(--dtype "${VLLM_DTYPE}")
fi

exec "${VLLM_PYTHON}" -m vllm.entrypoints.openai.api_server \
  --host "${VLLM_HOST}" \
  --port "${VLLM_PORT}" \
  --model "${MODEL}" \
  "${dtype_args[@]}" \
  --max-model-len "${VLLM_MAX_MODEL_LEN}" \
  --swap-space "${VLLM_SWAP_SPACE}" \
  --disable-log-requests
