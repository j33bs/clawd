#!/usr/bin/env bash
set -euo pipefail

PORT="8001"
PROBE_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --probe-only)
      PROBE_ONLY=1
      shift
      ;;
    *)
      PORT="$1"
      shift
      ;;
  esac
done

emit_info() {
  local line="$1"
  echo "$line"
  if command -v systemd-cat >/dev/null 2>&1; then
    printf '%s\n' "$line" | systemd-cat -t openclaw-vllm-port-guard -p info || true
  fi
}

emit_warn() {
  local line="$1"
  echo "$line"
  if command -v systemd-cat >/dev/null 2>&1; then
    printf '%s\n' "$line" | systemd-cat -t openclaw-vllm-port-guard -p warning || true
  fi
}

find_listener_line() {
  local ss_cmd="${OPENCLAW_PORT_GUARD_SS_CMD:-ss -ltnp}"
  bash -lc "$ss_cmd" 2>/dev/null | awk -v port="$PORT" '
    NR > 1 && $4 ~ ("[:.]" port "$") {
      print $0
      exit 0
    }
  '
}

extract_pid() {
  local line="$1"
  printf '%s' "$line" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1
}

pid_cmdline() {
  local pid="$1"
  if [[ -r "/proc/$pid/cmdline" ]]; then
    tr '\0' ' ' <"/proc/$pid/cmdline" | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//'
    return 0
  fi
  ps -p "$pid" -o args= 2>/dev/null | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//'
}

is_reclaimable_cmd() {
  local cmd_lower="$1"
  [[ "$cmd_lower" == *"vllm"* ]] || [[ "$cmd_lower" == *"openclaw-vllm"* ]]
}

line="$(find_listener_line || true)"
if [[ -z "$line" ]]; then
  emit_info "VLLM_PORT_OK port=$PORT"
  exit 0
fi

pid="$(extract_pid "$line")"
if [[ -z "$pid" ]]; then
  emit_warn "VLLM_PORT_STUCK port=$PORT reason=pid_unresolved listener=\"$line\""
  exit 42
fi

cmd="$(pid_cmdline "$pid")"
cmd="${cmd:-<unknown>}"
cmd_lower="$(printf '%s' "$cmd" | tr '[:upper:]' '[:lower:]')"

if ! is_reclaimable_cmd "$cmd_lower"; then
  emit_warn "VLLM_PORT_HELD_UNKNOWN port=$PORT pid=$pid cmd=\"$cmd\""
  exit 42
fi

if [[ "$PROBE_ONLY" == "1" ]]; then
  emit_info "VLLM_PORT_HELD_VLLM port=$PORT pid=$pid cmd=\"$cmd\""
  exit 0
fi

emit_warn "VLLM_PORT_RECLAIM port=$PORT pid=$pid cmd=\"$cmd\""
kill "$pid" 2>/dev/null || true

for _ in $(seq 1 15); do
  sleep 0.2
  line_after="$(find_listener_line || true)"
  if [[ -z "$line_after" ]]; then
    emit_info "VLLM_PORT_RECLAIMED port=$PORT"
    exit 0
  fi
done

line_final="$(find_listener_line || true)"
if [[ -n "$line_final" ]]; then
  emit_warn "VLLM_PORT_STUCK port=$PORT listener=\"$line_final\""
else
  emit_warn "VLLM_PORT_STUCK port=$PORT"
fi
exit 42
