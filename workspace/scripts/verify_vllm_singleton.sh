#!/usr/bin/env bash
set -euo pipefail

PORT="${VLLM_PORT:-8001}"
SYS_UNIT="${VLLM_SYSTEM_UNIT:-vllm-assistant.service}"
USER_UNIT="${VLLM_USER_UNIT:-openclaw-vllm.service}"

fail=0

say() { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
bad() { printf 'FAIL: %s\n' "$*" >&2; fail=1; }

have() { command -v "$1" >/dev/null 2>&1; }

say "vLLM singleton invariant check"
say "  system unit: $SYS_UNIT"
say "  user unit:   $USER_UNIT"
say "  port:        $PORT"
say

if have systemctl; then
  sys_enabled="$(systemctl is-enabled "$SYS_UNIT" 2>/dev/null || true)"
  sys_active="$(systemctl is-active  "$SYS_UNIT" 2>/dev/null || true)"
  say "systemctl: $SYS_UNIT enabled=$sys_enabled active=$sys_active"
  [[ "$sys_enabled" == "enabled" ]] || bad "$SYS_UNIT is not enabled (got: $sys_enabled)"
  [[ "$sys_active"  == "active"  ]] || bad "$SYS_UNIT is not active (got: $sys_active)"
else
  warn "systemctl not found; cannot verify $SYS_UNIT"
fi

if have systemctl; then
  # User systemd may not be available depending on environment.
  if systemctl --user show-environment >/dev/null 2>&1; then
    user_enabled="$(systemctl --user is-enabled "$USER_UNIT" 2>/dev/null || true)"
    user_active="$(systemctl --user is-active  "$USER_UNIT" 2>/dev/null || true)"
    say "systemctl --user: $USER_UNIT enabled=$user_enabled active=$user_active"
    [[ "$user_enabled" != "enabled" ]] || bad "$USER_UNIT is enabled (must be disabled)"
    [[ "$user_active"  != "active"  ]] || bad "$USER_UNIT is active (must be inactive)"
  else
    warn "systemctl --user not available; cannot verify $USER_UNIT state"
  fi
else
  warn "systemctl not found; cannot verify $USER_UNIT state"
fi

say
if have ss; then
  listeners="$(ss -ltnp 2>/dev/null | grep -E "(:$PORT)\\b" || true)"
  count="$(printf '%s\n' "$listeners" | sed '/^\s*$/d' | wc -l | tr -d ' ')"
  say "listeners on :$PORT = $count"
  if [[ "$count" -eq 0 ]]; then
    bad "no listener detected on :$PORT"
  elif [[ "$count" -gt 1 ]]; then
    bad "multiple listeners detected on :$PORT"
    say "$listeners"
  else
    say "$listeners"
  fi
else
  warn "ss not found; cannot verify port binding"
fi

say
if have pgrep; then
  procs="$(pgrep -af 'vllm|openai\.api_server|api_server' || true)"
  if [[ -n "$procs" ]]; then
    say "vLLM-related processes:"
    printf '%s\n' "$procs"
  else
    warn "no vLLM-related processes found via pgrep (may be false negative)"
  fi
else
  warn "pgrep not found; cannot list processes"
fi

say
if [[ "$fail" -eq 0 ]]; then
  say "PASS: vLLM singleton invariant holds"
else
  bad "vLLM singleton invariant violated"
fi

exit "$fail"
