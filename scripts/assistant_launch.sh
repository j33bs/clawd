#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${OPENCLAW_ASSISTANT_RUNTIME:-vllm}"

case "$RUNTIME" in
  vllm)
    exec "$ROOT_DIR/scripts/vllm_launch_assistant.sh"
    ;;
  llamacpp)
    exec "$ROOT_DIR/scripts/llamacpp_launch_assistant.sh"
    ;;
  *)
    echo "OPENCLAW_ASSISTANT_RUNTIME_INVALID runtime=$RUNTIME" >&2
    exit 42
    ;;
esac
