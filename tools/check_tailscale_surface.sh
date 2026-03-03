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

systemd_checked=0
if command -v systemctl >/dev/null 2>&1; then
  systemd_checked=1
  systemd_state="$(systemctl is-active tailscaled 2>&1 || true)"
  case "${systemd_state}" in
    active) ;;
    *"Failed to connect to bus"*|*"System has not been booted with systemd"*|*"Operation not permitted"*)
      # Fallback path: systemctl unavailable in this execution context.
      systemd_checked=0
      ;;
    *)
      fail "tailscaled service is not active (state: ${systemd_state})"
      ;;
  esac
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
      127.0.0.1:*|\[::1\]:*) ;;
      *) fail "port ${port} exposed on non-loopback address (${listen_addr})" ;;
    esac
  done < <(ss -ltnH "( sport = :${port} )" | awk '{print $4}')
done

serve_status="$(tailscale serve status 2>&1 || true)"
if [[ -z "${serve_status}" ]]; then
  fail "tailscale serve status returned no output"
fi

serve_status_json="$(tailscale serve status --json 2>/dev/null || true)"
if [[ -z "${serve_status_json}" ]]; then
  fail "tailscale serve status json unavailable"
fi
if [[ "${serve_status_json}" == "{}" ]]; then
  fail "tailscale serve is not configured"
fi

allowed_local_targets=("127.0.0.1:18789")
gateway_port="${OPENCLAW_TAILSCALE_GATEWAY_PORT:-${OPENCLAW_GATEWAY_PORT:-}}"
if [[ -n "${gateway_port}" && "${gateway_port}" != "18789" ]]; then
  allowed_local_targets+=("127.0.0.1:${gateway_port}")
fi

validation_output="$(
  ALLOWED_TARGETS="$(IFS=,; echo "${allowed_local_targets[*]}")" \
  python3 - <<'PY' "${serve_status_json}"
import json
import os
import re
import sys
from urllib.parse import urlparse

raw_json = sys.argv[1]
allowed = set(filter(None, os.environ.get("ALLOWED_TARGETS", "").split(",")))

try:
    parsed = json.loads(raw_json)
except json.JSONDecodeError as exc:
    print(f"FAIL: invalid tailscale serve status json: {exc}")
    raise SystemExit(1)

urls = []

def walk(value):
    if isinstance(value, dict):
        for v in value.values():
            walk(v)
        return
    if isinstance(value, list):
        for v in value:
            walk(v)
        return
    if isinstance(value, str) and re.match(r"^https?://", value):
        urls.append(value)

walk(parsed)

if not urls:
    print("FAIL: tailscale serve has no proxy targets")
    raise SystemExit(1)

for url in urls:
    parsed_url = urlparse(url)
    host = parsed_url.hostname or ""
    port = parsed_url.port
    if not host or port is None:
        print(f"FAIL: tailscale serve target missing host/port ({url})")
        raise SystemExit(1)
    if host != "127.0.0.1":
        print(f"FAIL: tailscale serve target must be loopback; got {url}")
        raise SystemExit(1)
    hostport = f"{host}:{port}"
    if hostport not in allowed:
        print(f"FAIL: tailscale serve target not allowlisted ({hostport})")
        raise SystemExit(1)
PY
)"

if [[ -n "${validation_output}" ]]; then
  fail "${validation_output#FAIL: }"
fi
