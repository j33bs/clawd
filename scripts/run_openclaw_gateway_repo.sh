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
BIND_INPUT="${OPENCLAW_GATEWAY_BIND:-loopback}"
case "$BIND_INPUT" in
  127.0.0.1|localhost) BIND_MODE="loopback" ;;
  loopback|lan|tailnet|auto|custom) BIND_MODE="$BIND_INPUT" ;;
  *) BIND_MODE="loopback" ;;
esac

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
echo "OPENCLAW_GATEWAY_BIND=${BIND_MODE} OPENCLAW_GATEWAY_PORT=${PORT}" >&2

exec openclaw gateway run --bind "${BIND_MODE}" --port "${PORT}"
