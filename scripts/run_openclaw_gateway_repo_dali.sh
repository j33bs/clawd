#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export OPENCLAW_QUIESCE=0

if [[ -z "${OPENCLAW_PROVIDER_ALLOWLIST:-}" ]]; then
  export OPENCLAW_PROVIDER_ALLOWLIST="local_vllm"
fi
if [[ -z "${OPENCLAW_DEFAULT_PROVIDER:-}" ]]; then
  export OPENCLAW_DEFAULT_PROVIDER="local_vllm"
fi

OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"

if [[ -z "${OPENCLAW_BIN}" || ! -x "${OPENCLAW_BIN}" ]]; then
  echo "gateway_repo_runner: missing openclaw binary at ${OPENCLAW_BIN}" >&2
  exit 1
fi
if [[ ! -f "${REPO_ROOT}/.runtime/openclaw/openclaw.mjs" ]]; then
  echo "gateway_repo_runner: missing repo runtime at ${REPO_ROOT}/.runtime/openclaw/openclaw.mjs" >&2
  exit 1
fi

cd "${REPO_ROOT}"
HEAD_SHA="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "gateway_repo_runner: repo=${REPO_ROOT} head=${HEAD_SHA} allowlist=${OPENCLAW_PROVIDER_ALLOWLIST}"

exec "${OPENCLAW_BIN}" gateway --port "${GATEWAY_PORT}" "$@"
