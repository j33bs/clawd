#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-/models/controller.gguf}"
PORT="${2:-8000}"

python -m llama_cpp.server \
  --model "${MODEL_PATH}" \
  --chat_format functionary-v2 \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --n_gpu_layers -1
