#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
EDGE_ENTRYPOINT="${OPENCLAW_ENTRYPOINT:-${REPO_ROOT}/scripts/system2_http_edge.js}"

GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND:-loopback}"
EDGE_PORT="${OPENCLAW_EDGE_PORT:-18792}"
EDGE_BIND="${OPENCLAW_EDGE_BIND:-127.0.0.1}"
EDGE_UPSTREAM_HOST="${OPENCLAW_EDGE_UPSTREAM_HOST:-127.0.0.1}"
EDGE_UPSTREAM_PORT="${OPENCLAW_EDGE_UPSTREAM_PORT:-${GATEWAY_PORT}}"

if [[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]]; then
  echo "OPENCLAW_GATEWAY_TOKEN is required" >&2
  exit 1
fi

# Reuse the existing gateway token for local machine-edge auth unless explicitly overridden.
export OPENCLAW_EDGE_TOKENS="${OPENCLAW_EDGE_TOKENS:-gateway:${OPENCLAW_GATEWAY_TOKEN}}"
export OPENCLAW_EDGE_ALLOW_BEARER_LOOPBACK="${OPENCLAW_EDGE_ALLOW_BEARER_LOOPBACK:-1}"
export OPENCLAW_EDGE_BIND="${EDGE_BIND}"
export OPENCLAW_EDGE_PORT="${EDGE_PORT}"
export OPENCLAW_EDGE_UPSTREAM_HOST="${EDGE_UPSTREAM_HOST}"
export OPENCLAW_EDGE_UPSTREAM_PORT="${EDGE_UPSTREAM_PORT}"
export OPENCLAW_REPO_RUNTIME="${OPENCLAW_REPO_RUNTIME:-system2_http_edge}"
export OPENCLAW_ENTRYPOINT="${EDGE_ENTRYPOINT}"

cd "${REPO_ROOT}"

node "${EDGE_ENTRYPOINT}" &
EDGE_PID=$!

cleanup() {
  if kill -0 "${EDGE_PID}" >/dev/null 2>&1; then
    kill "${EDGE_PID}" >/dev/null 2>&1 || true
    wait "${EDGE_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if "${OPENCLAW_BIN}" gateway --help >/dev/null 2>&1; then
  exec "${OPENCLAW_BIN}" gateway --bind "${GATEWAY_BIND}" --port "${GATEWAY_PORT}"
fi

exec "${OPENCLAW_BIN}"
