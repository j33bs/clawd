#!/usr/bin/env bash
# ============================================================================
# vllm_launch_optimal.sh — RTX 3090 tuned launch for Qwen2.5-14B AWQ
# ============================================================================
#
# Hardware context
# ----------------
#   GPU    : NVIDIA GeForce RTX 3090 (GA102)
#   VRAM   : 24 GB GDDR6X
#   CUDA   : 13.1 / Driver 590.48.01
#   Model  : Qwen2.5-14B-Instruct AWQ (4-bit, ~8 GB model weights on GPU)
#   vLLM   : 0.15.1
#
# What each flag does
# -------------------
#   --served-model-name local-assistant
#       Stable alias returned by /v1/models — keeps client code independent
#       of the underlying model path.
#
#   --quantization awq
#       4-bit AWQ quantization.  Qwen2.5-14B AWQ uses ~8 GB VRAM vs ~28 GB
#       at fp16, leaving 14+ GB for KV cache and concurrent sequences.
#
#   --dtype auto
#       Let vLLM pick fp16/bf16 for compute (Ampere = bf16 native).
#
#   --gpu-memory-utilization 0.90
#       Reserve 10% (~2.4 GB) for CUDA context, Xorg, and other processes.
#       At 93%+ the Xorg + browser processes cause OOM; 90% is the sweet spot.
#
#   --max-model-len 32768
#       Qwen2.5-14B supports 128K but KV cache grows linearly with ctx length.
#       32K gives ~5 concurrent long requests within our VRAM budget.
#       (Current config uses 16384; 32768 doubles context while staying safe.)
#
#   --max-num-seqs 16
#       PagedAttention can batch up to 16 concurrent sequences.
#       The KV cache dynamically allocates pages, so unused sequences cost 0.
#       Set high here; the ConcurrencyTuner in concurrency_tuner.js enforces
#       the effective limit based on real-time VRAM pressure.
#
#   --enable-chunked-prefill
#       Splits long prompts into chunks processed across multiple forward passes.
#       Prevents a single 32K-token prompt from monopolising the GPU for seconds,
#       enabling better interleaving with shorter concurrent requests.
#       Critical for interactive latency when mixing short and long contexts.
#
#   --max-num-batched-tokens 8192
#       Maximum tokens processed in a single forward pass (chunked prefill unit).
#       8192 = 2× the default, balancing throughput vs first-token latency.
#
#   --enable-prefix-caching
#       RadixAttention: reuses KV cache blocks for identical prompt prefixes.
#       Every request that shares the same system prompt gets its prefix KV
#       entries for free.  Hit rate was 38% in initial measurements (32/84 tokens).
#       Expect 60–80% once the warmup script runs on startup.
#
#   --enable-auto-tool-choice --tool-call-parser hermes
#       Enables Hermes-format tool call parsing at the vLLM level.
#       The model generates structured JSON tool calls that vLLM parses and
#       returns in the standard OpenAI tool_calls response format.
#
#   --swap-space 8
#       8 GB of CPU RAM swap for KV cache overflow (we have 24 GB free RAM).
#       When all GPU KV cache pages are full, least-recently-used sequences
#       are swapped to CPU RAM instead of being preempted/re-computed.
#       Costs latency (PCIe bandwidth) but prevents context eviction.
#
#   --uvicorn-log-level warning
#       Suppress per-request HTTP logs in production (they're noisy and slow).
#
# Env overrides
# -------------
#   VLLM_MODEL       : model path (default: /opt/models/qwen2_5_14b_instruct_awq)
#   VLLM_PORT        : listen port (default: 8001)
#   VLLM_HOST        : listen host (default: 127.0.0.1)
#   VLLM_GPU_UTIL    : GPU memory utilization 0–1 (default: 0.90)
#   VLLM_CTX_LEN     : max model context length (default: 32768)
#   VLLM_MAX_SEQS    : max concurrent sequences (default: 16)
# ============================================================================

# Signal to clients that the server was started with Hermes tool parser
export OPENCLAW_VLLM_ENABLE_AUTO_TOOL_CHOICE=1
export OPENCLAW_VLLM_TOOL_CALL_PARSER=hermes
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV="$REPO_ROOT/.venv-vllm"

MODEL="${VLLM_MODEL:-/opt/models/qwen2_5_14b_instruct_awq}"
HOST="${VLLM_HOST:-127.0.0.1}"
PORT="${VLLM_PORT:-8001}"
GPU_UTIL="${VLLM_GPU_UTIL:-0.90}"
CTX_LEN="${VLLM_CTX_LEN:-32768}"
MAX_SEQS="${VLLM_MAX_SEQS:-16}"
if TUNED_MAX_SEQS="$(node "$REPO_ROOT/scripts/tune_concurrency.js" 2>/dev/null)"; then
  if [[ "$TUNED_MAX_SEQS" =~ ^[0-9]+$ ]] && [[ "$TUNED_MAX_SEQS" -gt 0 ]]; then
    MAX_SEQS="$TUNED_MAX_SEQS"
  fi
fi
export VLLM_MAX_SEQS="$MAX_SEQS"

echo "[vllm-launch] Starting vLLM 0.15.1 — RTX 3090 optimal config"
echo "[vllm-launch] Model  : $MODEL"
echo "[vllm-launch] Server : http://$HOST:$PORT"
echo "[vllm-launch] Context: ${CTX_LEN} tokens  |  Max seqs: ${MAX_SEQS}"
echo "[vllm-launch] GPU util cap: ${GPU_UTIL}"

"$VENV/bin/vllm" serve "$MODEL" \
    --served-model-name local-assistant \
    --host "$HOST" \
    --port "$PORT" \
    --quantization awq \
    --dtype auto \
    --gpu-memory-utilization "$GPU_UTIL" \
    --max-model-len "$CTX_LEN" \
    --max-num-seqs "$MAX_SEQS" \
    --enable-chunked-prefill \
    --max-num-batched-tokens 8192 \
    --enable-prefix-caching \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --swap-space 8 \
    --uvicorn-log-level warning \
    "$@" &
VLLM_PID=$!

READY=0
for _ in $(seq 1 60); do
  if curl -fsS "http://$HOST:$PORT/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done
if [[ "$READY" -eq 1 ]]; then
  if [[ -f "$REPO_ROOT/scripts/vllm_prefix_warmup.js" ]] && node "$REPO_ROOT/scripts/vllm_prefix_warmup.js"; then
    echo "[vllm-launch] prefix warmup executed"
  else
    echo "[vllm-launch] prefix warmup unavailable/failed (continuing)"
  fi
else
  echo "[vllm-launch] health not ready within timeout (skipping warmup)"
fi

wait "$VLLM_PID"
