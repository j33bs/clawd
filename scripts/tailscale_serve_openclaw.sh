#!/usr/bin/env bash
set -euo pipefail

TAILSCALE_BIN="${TAILSCALE_BIN:-tailscale}"
HTTPS_PORT="${OPENCLAW_TAILSCALE_HTTPS_PORT:-443}"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GATEWAY_HOST="${OPENCLAW_GATEWAY_HOST:-127.0.0.1}"
SERVE_PATH="${OPENCLAW_TAILSCALE_SERVE_PATH:-/}"
DRYRUN="${OPENCLAW_TAILSCALE_SERVE_DRYRUN:-0}"

case "$GATEWAY_HOST" in
  127.0.0.1|localhost|::1) ;;
  *)
    echo "FATAL: OPENCLAW_GATEWAY_HOST must stay loopback-only (127.0.0.1|localhost|::1); got: ${GATEWAY_HOST}" >&2
    exit 2
    ;;
esac

case "$SERVE_PATH" in
  /*) ;;
  *)
    echo "FATAL: OPENCLAW_TAILSCALE_SERVE_PATH must start with '/'; got: ${SERVE_PATH}" >&2
    exit 2
    ;;
esac

PROXY_URL="http://127.0.0.1:${GATEWAY_PORT}"
cmd=("$TAILSCALE_BIN" serve --yes --bg "--https=${HTTPS_PORT}" "$SERVE_PATH" "$PROXY_URL")

if [[ "$DRYRUN" == "1" ]]; then
  printf 'OPENCLAW_TAILSCALE_SERVE_DRYRUN_COMMAND='
  printf '%q ' "${cmd[@]}"
  printf '\n'
  exit 0
fi

"${cmd[@]}"
"$TAILSCALE_BIN" serve status
