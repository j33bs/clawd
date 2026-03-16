#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${OPENCLAW_VLLM_ASSISTANT_HOST:-127.0.0.1}"
PORT="${OPENCLAW_VLLM_ASSISTANT_PORT:-8001}"
MODEL_PATH="${OPENCLAW_ASSISTANT_MODEL_PATH:-${OPENCLAW_VLLM_ASSISTANT_MODEL_PATH:-}}"
SERVED_MODEL_NAME="${OPENCLAW_VLLM_ASSISTANT_SERVED_MODEL_NAME:-local-assistant}"
CTX_SIZE="${OPENCLAW_ASSISTANT_CTX_SIZE:-16384}"
N_GPU_LAYERS="${OPENCLAW_ASSISTANT_N_GPU_LAYERS:-999}"
CACHE_TYPE_K="${OPENCLAW_ASSISTANT_CACHE_TYPE_K:-q8_0}"
CACHE_TYPE_V="${OPENCLAW_ASSISTANT_CACHE_TYPE_V:-q8_0}"
REASONING_BUDGET="${OPENCLAW_ASSISTANT_REASONING_BUDGET:-0}"
CHAT_TEMPLATE_KWARGS="${OPENCLAW_ASSISTANT_CHAT_TEMPLATE_KWARGS:-}"
LLAMACPP_ROOT="${OPENCLAW_LLAMACPP_ROOT:-$ROOT_DIR/.runtime/llama.cpp-vulkan}"
SERVER_BIN="${OPENCLAW_LLAMACPP_SERVER_BIN:-}"

if [[ -z "$CHAT_TEMPLATE_KWARGS" ]]; then
  CHAT_TEMPLATE_KWARGS='{"enable_thinking":false}'
fi

if [[ -z "$SERVER_BIN" ]]; then
  if [[ -x "$LLAMACPP_ROOT/llama-server" ]]; then
    SERVER_BIN="$LLAMACPP_ROOT/llama-server"
  elif [[ -x "$LLAMACPP_ROOT/bin/llama-server" ]]; then
    SERVER_BIN="$LLAMACPP_ROOT/bin/llama-server"
  else
    SERVER_BIN="$(find "$LLAMACPP_ROOT" -type f -name llama-server 2>/dev/null | head -n1 || true)"
  fi
fi

if [[ -z "$MODEL_PATH" ]]; then
  echo "LLAMACPP_ASSISTANT_PREFLIGHT_FAILED reason=model_missing_env" >&2
  exit 42
fi

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "LLAMACPP_ASSISTANT_PREFLIGHT_FAILED reason=model_missing path=$MODEL_PATH" >&2
  exit 42
fi

if [[ -z "$SERVER_BIN" || ! -x "$SERVER_BIN" ]]; then
  echo "LLAMACPP_ASSISTANT_PREFLIGHT_FAILED reason=server_missing path=${SERVER_BIN:-unset}" >&2
  exit 42
fi

set +e
"$ROOT_DIR/scripts/ensure_port_free.sh" "$PORT"
PORT_GUARD_EC=$?
set -e
if [[ $PORT_GUARD_EC -ne 0 ]]; then
  echo "LLAMACPP_ASSISTANT_PREFLIGHT_FAILED reason=port_guard_failed port=$PORT exit_code=$PORT_GUARD_EC" >&2
  exit "$PORT_GUARD_EC"
fi

export LD_LIBRARY_PATH="${LLAMACPP_ROOT}:${LLAMACPP_ROOT}/lib:${LLAMACPP_ROOT}/bin:${LD_LIBRARY_PATH:-}"

echo "=== llamacpp_launch_assistant.sh ==="
echo "server=$SERVER_BIN host=$HOST port=$PORT model=$MODEL_PATH"
echo "served_model=$SERVED_MODEL_NAME ctx_size=$CTX_SIZE n_gpu_layers=$N_GPU_LAYERS cache_type_k=$CACHE_TYPE_K cache_type_v=$CACHE_TYPE_V"
echo "reasoning_budget=$REASONING_BUDGET chat_template_kwargs=$CHAT_TEMPLATE_KWARGS"

exec "$SERVER_BIN" \
  -m "$MODEL_PATH" \
  -a "$SERVED_MODEL_NAME" \
  --host "$HOST" \
  --port "$PORT" \
  -c "$CTX_SIZE" \
  -ngl "$N_GPU_LAYERS" \
  -ctk "$CACHE_TYPE_K" \
  -ctv "$CACHE_TYPE_V" \
  --jinja \
  --chat-template-kwargs "$CHAT_TEMPLATE_KWARGS" \
  --reasoning-budget "$REASONING_BUDGET" \
  --no-webui
