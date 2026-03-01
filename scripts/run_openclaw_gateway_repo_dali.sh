#!/usr/bin/env bash
set -euo pipefail

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

is_loopback_host() {
  local host_raw host
  host_raw="${1:-}"
  host="${host_raw#[}"
  host="${host%]}"
  host="${host%%:*}"
  case "${host}" in
    localhost|127.0.0.1|::1) return 0 ;;
    *) return 1 ;;
  esac
}

validate_port() {
  local raw="$1"
  if [[ ! "${raw}" =~ ^[0-9]+$ ]]; then
    echo "gateway_repo_runner: invalid OPENCLAW_GATEWAY_PORT (${raw})" >&2
    exit 1
  fi
  if (( raw < 1 || raw > 65535 )); then
    echo "gateway_repo_runner: OPENCLAW_GATEWAY_PORT out of range (${raw})" >&2
    exit 1
  fi
}

validate_control_ui_origins() {
  local raw origin host
  raw="${OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS:-}"
  [[ -n "${raw}" ]] || return 0
  IFS=',' read -r -a origins <<< "${raw}"
  for origin in "${origins[@]}"; do
    origin="$(printf '%s' "${origin}" | xargs)"
    [[ -n "${origin}" ]] || continue
    if [[ "${origin}" == *"*"* ]]; then
      echo "gateway_repo_runner: OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS rejects wildcard origin (${origin})" >&2
      exit 1
    fi
    if [[ ! "${origin}" =~ ^https?://[^[:space:]]+$ ]]; then
      echo "gateway_repo_runner: OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS requires valid http(s) origins (${origin})" >&2
      exit 1
    fi
    if [[ "${origin}" == http://* ]]; then
      host="${origin#http://}"
      host="${host%%/*}"
      if ! is_loopback_host "${host}"; then
        echo "gateway_repo_runner: insecure non-loopback http origin is not allowed (${origin})" >&2
        exit 1
      fi
    fi
  done
}

require_nonloopback_ack() {
  if ! is_truthy "${OPENCLAW_GATEWAY_ALLOW_NONLOOPBACK:-0}"; then
    echo "gateway_repo_runner: non-loopback bind requires OPENCLAW_GATEWAY_ALLOW_NONLOOPBACK=1" >&2
    exit 1
  fi
}

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$REPO_ROOT" ] && ! is_truthy "${OPENCLAW_GATEWAY_SKIP_WORKTREE_GUARD:-0}"; then
  "$REPO_ROOT/tools/guard_worktree_boundary.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${REPO_ROOT}" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

if [[ -z "${OPENCLAW_QUIESCE:-}" ]]; then
  if [[ "${NODE_ENV:-}" == "test" ]]; then
    export OPENCLAW_QUIESCE=1
  else
    export OPENCLAW_QUIESCE=0
  fi
fi

if [[ -z "${OPENCLAW_PROVIDER_ALLOWLIST:-}" ]]; then
  export OPENCLAW_PROVIDER_ALLOWLIST="local_vllm"
fi
if [[ -z "${OPENCLAW_DEFAULT_PROVIDER:-}" ]]; then
  export OPENCLAW_DEFAULT_PROVIDER="local_vllm"
fi

OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
BIND_MODE="$(printf '%s' "${OPENCLAW_GATEWAY_BIND_MODE:-loopback}" | tr '[:upper:]' '[:lower:]')"
AUTH_MODE="$(printf '%s' "${OPENCLAW_GATEWAY_AUTH_MODE:-}" | tr '[:upper:]' '[:lower:]')"
CUSTOM_BIND_HOST="${OPENCLAW_GATEWAY_CUSTOM_BIND_HOST:-}"

validate_port "${GATEWAY_PORT}"
validate_control_ui_origins

# Phase 1 (AIS-03, IAM-14): inject config overrides from env before launch.
INJECT_SCRIPT="${REPO_ROOT}/tools/inject_gateway_config_overrides.sh"
if [[ -x "${INJECT_SCRIPT}" ]]; then
  if [[ -z "${OPENCLAW_CONFIG_OVERRIDE_PATH:-}" && -n "${OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS:-}" ]]; then
    export OPENCLAW_CONFIG_OVERRIDE_PATH="${REPO_ROOT}/.runtime/openclaw/config_override.json"
  fi
  "${INJECT_SCRIPT}"
fi

case "${BIND_MODE}" in
  loopback|lan|tailnet|auto) ;;
  custom)
    if [[ -z "${CUSTOM_BIND_HOST}" ]]; then
      echo "gateway_repo_runner: OPENCLAW_GATEWAY_BIND_MODE=custom requires OPENCLAW_GATEWAY_CUSTOM_BIND_HOST" >&2
      exit 1
    fi
    if ! is_loopback_host "${CUSTOM_BIND_HOST}"; then
      require_nonloopback_ack
    fi
    ;;
  *)
    echo "gateway_repo_runner: invalid OPENCLAW_GATEWAY_BIND_MODE (${BIND_MODE})" >&2
    exit 1
    ;;
esac

if [[ "${BIND_MODE}" != "loopback" ]]; then
  if [[ "${BIND_MODE}" == "custom" ]] && is_loopback_host "${CUSTOM_BIND_HOST}"; then
    true
  else
    require_nonloopback_ack
  fi
fi

if [[ -z "${AUTH_MODE}" && "${BIND_MODE}" != "loopback" ]]; then
  AUTH_MODE="token"
fi
if [[ -n "${AUTH_MODE}" ]]; then
  case "${AUTH_MODE}" in
    token|password) ;;
    *)
      echo "gateway_repo_runner: invalid OPENCLAW_GATEWAY_AUTH_MODE (${AUTH_MODE})" >&2
      exit 1
      ;;
  esac
fi

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
echo "gateway_repo_runner: repo=${REPO_ROOT} head=${HEAD_SHA} allowlist=${OPENCLAW_PROVIDER_ALLOWLIST} bind=${BIND_MODE}"

PATCH_SCRIPT="${REPO_ROOT}/tools/apply_gateway_security_hardening.sh"
PATCH_MODE="$(printf '%s' "${OPENCLAW_GATEWAY_HARDEN_PATCH_MODE:-apply}" | tr '[:upper:]' '[:lower:]')"
if [[ -x "${PATCH_SCRIPT}" ]]; then
  case "${PATCH_MODE}" in
    apply) "${PATCH_SCRIPT}" ;;
    check) "${PATCH_SCRIPT}" --check ;;
    skip) ;;
    *)
      echo "gateway_repo_runner: invalid OPENCLAW_GATEWAY_HARDEN_PATCH_MODE (${PATCH_MODE})" >&2
      exit 1
      ;;
  esac
fi

gateway_args=(gateway --port "${GATEWAY_PORT}" --bind "${BIND_MODE}")
if [[ -n "${OPENCLAW_CONFIG_OVERRIDE_PATH:-}" && -f "${OPENCLAW_CONFIG_OVERRIDE_PATH}" ]]; then
  gateway_args+=(--config-override "${OPENCLAW_CONFIG_OVERRIDE_PATH}")
fi
if [[ "${AUTH_MODE}" == "token" ]]; then
  if [[ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]]; then
    echo "gateway_repo_runner: OPENCLAW_GATEWAY_TOKEN is required when auth mode is token" >&2
    exit 1
  fi
  gateway_args+=(--auth token --token "${OPENCLAW_GATEWAY_TOKEN}")
elif [[ "${AUTH_MODE}" == "password" ]]; then
  if [[ -z "${OPENCLAW_GATEWAY_PASSWORD:-}" ]]; then
    echo "gateway_repo_runner: OPENCLAW_GATEWAY_PASSWORD is required when auth mode is password" >&2
    exit 1
  fi
  gateway_args+=(--auth password --password "${OPENCLAW_GATEWAY_PASSWORD}")
fi

exec "${OPENCLAW_BIN}" "${gateway_args[@]}" "$@"
