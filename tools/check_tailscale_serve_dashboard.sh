#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

if ! command -v tailscale >/dev/null 2>&1; then
  fail "tailscale not installed (tailscale binary missing)"
fi

if ! tailscale status >/dev/null 2>&1; then
  fail "tailscale status failed"
fi

serve_status_out=""
if ! serve_status_out="$(tailscale serve status 2>&1)"; then
  if grep -qiE 'access denied|permission|run: sudo|requires sudo' <<<"${serve_status_out}"; then
    echo "tailscale serve status requires sudo on this system; run: sudo tools/apply_tailscale_serve_dashboard.sh" >&2
    exit 1
  fi
  fail "tailscale serve status failed"
fi

if ! grep -q "18789" <<<"${serve_status_out}" || ! grep -q "127.0.0.1:18789" <<<"${serve_status_out}"; then
  fail "tailscale serve dashboard mapping missing (expected 18789 -> 127.0.0.1:18789)"
fi

if ! command -v ss >/dev/null 2>&1; then
  fail "ss not found"
fi

listen_lines="$(ss -tulpn 2>/dev/null | grep -E ':(18789)\b' || true)"
if [[ -z "${listen_lines}" ]]; then
  fail "dashboard port 18789 is not listening"
fi

saw_loopback=0
while IFS= read -r line; do
  [[ -n "${line}" ]] || continue
  local_addr="$(awk '{print $5}' <<<"${line}")"
  case "${local_addr}" in
    127.0.0.1:18789|\[::1\]:18789)
      saw_loopback=1
      ;;
    0.0.0.0:18789|\[::\]:18789|:::18789|*:18789)
      fail "dashboard port 18789 is publicly bound (${local_addr})"
      ;;
    *:18789)
      fail "dashboard port 18789 is bound to non-loopback address (${local_addr})"
      ;;
  esac
done <<<"${listen_lines}"

if [[ "${saw_loopback}" -ne 1 ]]; then
  fail "dashboard port 18789 is bound to non-loopback address"
fi
