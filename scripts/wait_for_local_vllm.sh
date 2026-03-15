#!/usr/bin/env bash
set -euo pipefail

PORT="${OPENCLAW_VLLM_ASSISTANT_PORT:-8001}"
TIMEOUT_SEC="${OPENCLAW_VLLM_WAIT_TIMEOUT_SEC:-180}"
SLEEP_SEC="${OPENCLAW_VLLM_WAIT_POLL_SEC:-2}"
URL="http://127.0.0.1:${PORT}/v1/models"

deadline=$((SECONDS + TIMEOUT_SEC))

while (( SECONDS < deadline )); do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "WAIT_OK local_vllm url=$URL"
    exit 0
  fi
  sleep "$SLEEP_SEC"
done

echo "WAIT_TIMEOUT local_vllm url=$URL timeout_sec=$TIMEOUT_SEC" >&2
exit 42
