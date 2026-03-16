#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${1:-Qwen/Qwen3-14B}"
PORT="${2:-8000}"
MAX_LEN="${3:-32768}"

vllm serve "${MODEL_NAME}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --gpu-memory-utilization 0.92 \
  --max-model-len "${MAX_LEN}"
