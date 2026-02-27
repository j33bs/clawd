#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

if ! command -v tailscale >/dev/null 2>&1; then
  fail "tailscale not installed (tailscale binary missing)"
fi

if ! tailscale version >/dev/null 2>&1; then
  fail "tailscale installed but version command failed"
fi

if ! command -v systemctl >/dev/null 2>&1; then
  fail "systemctl missing; cannot verify tailscaled service state"
fi

if [[ "$(systemctl is-active tailscaled 2>/dev/null || true)" != "active" ]]; then
  fail "tailscaled service is not active"
fi

if ! tailscale status >/dev/null 2>&1; then
  fail "tailscale status failed"
fi

if ! command -v ss >/dev/null 2>&1; then
  fail "ss missing; cannot verify listen bindings"
fi

watch_ports=(18789 8001)
if [[ -n "${OPENCLAW_GATEWAY_PORT:-}" ]]; then
  watch_ports+=("${OPENCLAW_GATEWAY_PORT}")
fi

for port in "${watch_ports[@]}"; do
  [[ -n "${port}" ]] || continue
  while IFS= read -r listen_addr; do
    [[ -n "${listen_addr}" ]] || continue
    case "${listen_addr}" in
      127.0.0.1:*|[::1]:*) ;;
      *) fail "port ${port} exposed on non-loopback address (${listen_addr})" ;;
    esac
  done < <(ss -ltnH "( sport = :${port} )" | awk '{print $4}')
done

serve_status="$(tailscale serve status 2>&1 || true)"
if [[ -z "${serve_status}" ]]; then
  fail "tailscale serve status returned no output"
fi
if grep -qiE 'no serve config|serve is not configured|not serving' <<<"${serve_status}"; then
  fail "tailscale serve is not configured"
fi

mapfile -t targets < <(sed -nE 's/.*proxy (https?:\/\/[^[:space:]]+).*/\1/p' <<<"${serve_status}")
if ((${#targets[@]} == 0)); then
  fail "tailscale serve has no proxy targets"
fi

allowed_local_targets=("127.0.0.1:18789")
if [[ -n "${OPENCLAW_GATEWAY_PORT:-}" && "${OPENCLAW_GATEWAY_PORT}" != "18789" ]]; then
  allowed_local_targets+=("127.0.0.1:${OPENCLAW_GATEWAY_PORT}")
fi

for target in "${targets[@]}"; do
  target_no_scheme="${target#http://}"
  target_no_scheme="${target_no_scheme#https://}"
  hostport="${target_no_scheme%%/*}"
  host="${hostport%:*}"
  port="${hostport##*:}"

  if [[ "${host}" != "127.0.0.1" ]]; then
    fail "tailscale serve target must be loopback; got ${target}"
  fi

  allowed=0
  for allowed_target in "${allowed_local_targets[@]}"; do
    if [[ "${host}:${port}" == "${allowed_target}" ]]; then
      allowed=1
      break
    fi
  done
  if ((allowed == 0)); then
    fail "tailscale serve target not allowlisted (${host}:${port})"
  fi
done

echo "ok"
