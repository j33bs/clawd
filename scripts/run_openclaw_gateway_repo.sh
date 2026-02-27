#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/Users/heathyeager/clawd"
if [[ ! -d "$REPO_ROOT" ]]; then
  echo "FATAL: repo root missing: $REPO_ROOT" >&2
  exit 1
fi
cd "$REPO_ROOT"

export NODE_ENV="${NODE_ENV:-production}"
export OPENCLAW_QUIESCE="${OPENCLAW_QUIESCE:-0}"
export OPENCLAW_EDGE_BIND="${OPENCLAW_EDGE_BIND:-127.0.0.1}"
export OPENCLAW_EDGE_PORT="${OPENCLAW_EDGE_PORT:-18789}"
export OPENCLAW_EDGE_UPSTREAM_HOST="${OPENCLAW_EDGE_UPSTREAM_HOST:-127.0.0.1}"
export OPENCLAW_EDGE_UPSTREAM_PORT="${OPENCLAW_EDGE_UPSTREAM_PORT:-18790}"

if [[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]]; then
  echo "FATAL: OPENCLAW_GATEWAY_TOKEN is required for edge auth" >&2
  exit 1
fi
if [[ -z "${OPENCLAW_EDGE_TOKENS:-}" ]]; then
  export OPENCLAW_EDGE_TOKENS="gateway:${OPENCLAW_GATEWAY_TOKEN}"
fi

UPSTREAM_NODE="${OPENCLAW_UPSTREAM_NODE:-/opt/homebrew/Cellar/node/25.6.0/bin/node}"
UPSTREAM_ENTRY="${OPENCLAW_UPSTREAM_ENTRY:-$HOME/.npm-global/lib/node_modules/openclaw/dist/entry.js}"
if [[ ! -x "$UPSTREAM_NODE" ]]; then
  echo "FATAL: upstream node binary missing: $UPSTREAM_NODE" >&2
  exit 1
fi
if [[ ! -f "$UPSTREAM_ENTRY" ]]; then
  echo "FATAL: upstream gateway entry missing: $UPSTREAM_ENTRY" >&2
  exit 1
fi

repo_sha="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
repo_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
entrypoint="${OPENCLAW_ENTRYPOINT:-$REPO_ROOT/scripts/system2_http_edge.js}"
export OPENCLAW_REPO_SHA="$repo_sha"
export OPENCLAW_REPO_BRANCH="$repo_branch"
export OPENCLAW_ENTRYPOINT="$entrypoint"
echo "OPENCLAW_REPO_RUNTIME=system2_http_edge" >&2
echo "OPENCLAW_REPO_ROOT=${REPO_ROOT}" >&2
echo "OPENCLAW_REPO_SHA=${repo_sha}" >&2
echo "OPENCLAW_REPO_BRANCH=${repo_branch}" >&2
echo "OPENCLAW_ENTRYPOINT=${OPENCLAW_ENTRYPOINT}" >&2
echo "OPENCLAW_BUILD repo_sha=${OPENCLAW_REPO_SHA} branch=${OPENCLAW_REPO_BRANCH} entrypoint=${OPENCLAW_ENTRYPOINT}" >&2
echo "OPENCLAW_UPSTREAM_ENTRY=${UPSTREAM_ENTRY}" >&2
echo "OPENCLAW_EDGE_PORT=${OPENCLAW_EDGE_PORT} OPENCLAW_EDGE_UPSTREAM_PORT=${OPENCLAW_EDGE_UPSTREAM_PORT}" >&2

"$UPSTREAM_NODE" "$UPSTREAM_ENTRY" gateway --port "$OPENCLAW_EDGE_UPSTREAM_PORT" &
UPSTREAM_PID=$!

cleanup() {
  local rc=$?
  if kill -0 "$UPSTREAM_PID" >/dev/null 2>&1; then
    kill "$UPSTREAM_PID" >/dev/null 2>&1 || true
    wait "$UPSTREAM_PID" 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

node "$OPENCLAW_ENTRYPOINT"
