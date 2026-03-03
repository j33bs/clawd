#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENSURE_PORT_FREE="${ROOT}/scripts/ensure_port_free.sh"
PORT="${OPENCLAW_VLLM_PORT:-8001}"
MODE="preflight"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preflight)
      MODE="preflight"
      shift
      ;;
    --nightly)
      MODE="nightly"
      shift
      ;;
    --port)
      PORT="${2:-$PORT}"
      shift 2
      ;;
    *)
      echo "VLLM_GATE_WARN mode=$MODE reason=unknown_arg arg=$1"
      shift
      ;;
  esac
done

if [[ ! -x "$ENSURE_PORT_FREE" ]]; then
  echo "VLLM_GATE_WARN mode=$MODE reason=missing_port_guard path=$ENSURE_PORT_FREE"
  [[ "$MODE" == "preflight" ]] && exit 42 || exit 0
fi

run_health_probe() {
  local url="http://127.0.0.1:${PORT}/health"
  if [[ -n "${OPENCLAW_GATE_CURL_CMD:-}" ]]; then
    bash -lc "${OPENCLAW_GATE_CURL_CMD} \"$url\"" >/dev/null 2>&1
  else
    curl -sf "$url" >/dev/null 2>&1
  fi
}

set +e
probe_output="$(
  OPENCLAW_PORT_GUARD_SS_CMD="${OPENCLAW_GATE_SS_CMD:-ss -ltnp}" \
    "$ENSURE_PORT_FREE" --probe-only "$PORT" 2>&1
)"
probe_ec=$?
set -e

owner="unknown"
pid=""
cmd=""
if grep -q "VLLM_PORT_OK" <<<"$probe_output"; then
  owner="free"
elif grep -q "VLLM_PORT_HELD_VLLM" <<<"$probe_output"; then
  owner="vllm_like"
elif grep -q "VLLM_PORT_HELD_UNKNOWN" <<<"$probe_output"; then
  owner="unknown"
fi

pid="$(sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$probe_output" | head -n1)"
cmd="$(sed -n 's/.*cmd=\"\(.*\)\".*/\1/p' <<<"$probe_output" | head -n1)"

health="down"
if run_health_probe; then
  health="ok"
fi

echo "VLLM_GATE mode=$MODE port=$PORT port_owner=$owner pid=${pid:-} cmd=\"${cmd:-}\" health=$health probe_ec=$probe_ec"

if [[ "$owner" == "unknown" ]]; then
  echo "HINT: vLLM blocked - port $PORT held by unknown process (pid=${pid:-unknown}, cmd=\"${cmd:-<unknown>}\"). Stop it or free :$PORT, then restart openclaw-vllm.service."
fi
if [[ "$health" == "down" ]]; then
  echo "HINT: vLLM health endpoint is down on :$PORT. Check openclaw-vllm.service logs and restart the unit."
fi

if [[ "$MODE" == "nightly" ]]; then
  if [[ "$owner" == "unknown" || "$health" == "down" || $probe_ec -ne 0 ]]; then
    echo "VLLM_GATE_WARN mode=nightly owner=$owner health=$health probe_ec=$probe_ec"
  fi
  exit 0
fi

if [[ "$owner" == "unknown" || "$health" == "down" || $probe_ec -ne 0 ]]; then
  exit 42
fi
exit 0
