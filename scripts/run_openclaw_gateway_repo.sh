#!/usr/bin/env bash
set -euo pipefail

SOURCE_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SOURCE_PATH}")" && pwd)"
REPO_ROOT="${OPENCLAW_HOME:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
if [[ ! -d "$REPO_ROOT" ]]; then
  echo "FATAL: repo root missing: $REPO_ROOT" >&2
  exit 1
fi
cd "$REPO_ROOT"

export NODE_ENV="${NODE_ENV:-production}"
export OPENCLAW_QUIESCE="${OPENCLAW_QUIESCE:-0}"
PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
BIND_ADDR="${OPENCLAW_GATEWAY_BIND:-loopback}"

repo_sha="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
repo_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
entrypoint="${OPENCLAW_ENTRYPOINT:-openclaw gateway run}"
export OPENCLAW_REPO_SHA="$repo_sha"
export OPENCLAW_REPO_BRANCH="$repo_branch"
export OPENCLAW_ENTRYPOINT="$entrypoint"
echo "OPENCLAW_REPO_RUNTIME=openclaw_gateway" >&2
echo "OPENCLAW_REPO_ROOT=${REPO_ROOT}" >&2
echo "OPENCLAW_REPO_SHA=${repo_sha}" >&2
echo "OPENCLAW_REPO_BRANCH=${repo_branch}" >&2
echo "OPENCLAW_ENTRYPOINT=${OPENCLAW_ENTRYPOINT}" >&2
echo "OPENCLAW_BUILD repo_sha=${OPENCLAW_REPO_SHA} branch=${OPENCLAW_REPO_BRANCH} entrypoint=${OPENCLAW_ENTRYPOINT}" >&2
echo "OPENCLAW_GATEWAY_BIND=${BIND_ADDR} OPENCLAW_GATEWAY_PORT=${PORT}" >&2

# Tailscale optional transport binding (CBP safe-mode)
if [ "$BIND_ADDR" = "tailscale" ]; then
  TS_IP="$(tailscale ip -4 | head -n1)"
  if [ -z "$TS_IP" ]; then
    echo "FATAL: tailscale mode requested but tailscale IPv4 is unavailable" >&2
    exit 1
  fi
  exec openclaw gateway run --bind tailnet --port "${PORT}"
else
  exec openclaw gateway run --bind loopback --port "${PORT}"
fi
