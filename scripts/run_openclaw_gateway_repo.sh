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
DRYRUN="${OPENCLAW_WRAPPER_DRYRUN:-0}"
BIND_INPUT="${OPENCLAW_GATEWAY_BIND:-loopback}"
CONTROL_UI_MODE="${OPENCLAW_TAILNET_CONTROL_UI:-local}"
TAILSCALE_IP_OVERRIDE="${OPENCLAW_TAILSCALE_IP_OVERRIDE:-}"

case "$BIND_INPUT" in
  ""|127.0.0.1|localhost|loopback) BIND_MODE="loopback" ;;
  tailnet) BIND_MODE="tailnet" ;;
  *)
    echo "FATAL: unsupported OPENCLAW_GATEWAY_BIND=${BIND_INPUT} (allowed: loopback|tailnet)" >&2
    exit 2
    ;;
esac

trim() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

TS_IP=""
RUNTIME_BIND="$BIND_MODE"
RESOLVED_BIND_HOST="127.0.0.1"
ALLOWED_ORIGINS_COUNT=0
ALLOWED_ORIGINS_JSON="[]"
OVERLAY_CONFIG_PATH=""
OVERLAY_MECHANISM=""

if [[ "$BIND_MODE" == "tailnet" ]]; then
  if [[ -n "$TAILSCALE_IP_OVERRIDE" ]]; then
    TS_IP="$(trim "$TAILSCALE_IP_OVERRIDE")"
  else
    if ! command -v tailscale >/dev/null 2>&1; then
      echo "FATAL: OPENCLAW_GATEWAY_BIND=tailnet requires tailscale CLI (or set OPENCLAW_TAILSCALE_IP_OVERRIDE)" >&2
      exit 2
    fi
    TS_IP="$(tailscale ip -4 | head -n1 | tr -d '[:space:]')"
  fi
  if [[ -z "$TS_IP" ]]; then
    echo "FATAL: OPENCLAW_GATEWAY_BIND=tailnet requires a tailscale IPv4 address (set OPENCLAW_TAILSCALE_IP_OVERRIDE for deterministic runs)" >&2
    exit 2
  fi
  case "$TS_IP" in
    ""|0.0.0.0|::)
      echo "FATAL: refusing unsafe tailnet bind host: ${TS_IP:-<empty>}" >&2
      exit 2
      ;;
  esac

  RESOLVED_BIND_HOST="$TS_IP"
  RUNTIME_BIND="tailnet"

  case "$CONTROL_UI_MODE" in
    off)
      OVERLAY_MECHANISM="overlay_config"
      ;;
    allowlist)
      ALLOWED_RAW="${OPENCLAW_TAILNET_ALLOWED_ORIGINS:-}"
      if [[ -z "$ALLOWED_RAW" ]]; then
        echo "FATAL: OPENCLAW_TAILNET_CONTROL_UI=allowlist requires OPENCLAW_TAILNET_ALLOWED_ORIGINS" >&2
        exit 2
      fi
      ALLOWED_ORIGINS_JSON="$(printf '%s' "$ALLOWED_RAW" | node -e '
const raw = require("node:fs").readFileSync(0, "utf8");
const list = raw.split(",").map((v) => v.trim()).filter(Boolean);
if (list.length === 0) {
  console.error("FATAL: OPENCLAW_TAILNET_ALLOWED_ORIGINS produced an empty allowlist");
  process.exit(2);
}
process.stdout.write(JSON.stringify(list));
')"
      ALLOWED_ORIGINS_COUNT="$(printf '%s' "$ALLOWED_ORIGINS_JSON" | node -e 'const v = JSON.parse(require("node:fs").readFileSync(0, "utf8")); process.stdout.write(String(v.length));')"
      OVERLAY_MECHANISM="overlay_config"
      ;;
    ""|local)
      echo "FATAL: tailnet bind requires OPENCLAW_TAILNET_CONTROL_UI=off OR allowlist + OPENCLAW_TAILNET_ALLOWED_ORIGINS" >&2
      exit 2
      ;;
    *)
      echo "FATAL: unsupported OPENCLAW_TAILNET_CONTROL_UI=${CONTROL_UI_MODE} (allowed: local|off|allowlist)" >&2
      exit 2
      ;;
  esac
fi

case "$RESOLVED_BIND_HOST" in
  ""|0.0.0.0|::)
    echo "FATAL: refusing unsafe bind host: ${RESOLVED_BIND_HOST:-<empty>}" >&2
    exit 2
    ;;
esac

if [[ -n "$OVERLAY_MECHANISM" ]]; then
  BASE_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-}"
  if [[ -z "$BASE_CONFIG_PATH" ]]; then
    BASE_CONFIG_PATH="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/openclaw.json"
  fi
  OVERLAY_CONFIG_PATH="$(mktemp "${TMPDIR:-/tmp}/openclaw-gateway-config.XXXXXX")"
  if [[ -f "$BASE_CONFIG_PATH" ]]; then
    cp "$BASE_CONFIG_PATH" "$OVERLAY_CONFIG_PATH"
  else
    printf '{}\n' > "$OVERLAY_CONFIG_PATH"
  fi

  if [[ "$CONTROL_UI_MODE" == "off" ]]; then
    OPENCLAW_CONFIG_PATH="$OVERLAY_CONFIG_PATH" openclaw config set --strict-json gateway.controlUi.enabled false >/dev/null
    ALLOWED_ORIGINS_COUNT=0
  elif [[ "$CONTROL_UI_MODE" == "allowlist" ]]; then
    OPENCLAW_CONFIG_PATH="$OVERLAY_CONFIG_PATH" openclaw config set --strict-json gateway.controlUi.enabled true >/dev/null
    OPENCLAW_CONFIG_PATH="$OVERLAY_CONFIG_PATH" openclaw config set --strict-json gateway.controlUi.allowedOrigins "$ALLOWED_ORIGINS_JSON" >/dev/null
  fi
fi

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
echo "OPENCLAW_GATEWAY_BIND=${RUNTIME_BIND} OPENCLAW_GATEWAY_PORT=${PORT}" >&2
echo "OPENCLAW_TAILNET_MODE bind=${RUNTIME_BIND} control_ui=${CONTROL_UI_MODE} allowed_origins_count=${ALLOWED_ORIGINS_COUNT}" >&2
echo "OPENCLAW_TAILNET_BIND_HOST=${RESOLVED_BIND_HOST}" >&2
if [[ -n "$OVERLAY_MECHANISM" ]]; then
  echo "OPENCLAW_TAILNET_CONTROL_UI_MECHANISM=${OVERLAY_MECHANISM}" >&2
  echo "OPENCLAW_CONFIG_PATH=${OVERLAY_CONFIG_PATH}" >&2
fi

cmd=(openclaw gateway run --bind "${RUNTIME_BIND}" --port "${PORT}")

if [[ "$DRYRUN" == "1" ]]; then
  printf 'OPENCLAW_WRAPPER_DRYRUN_COMMAND=' >&2
  printf '%q ' "${cmd[@]}" >&2
  printf '\n' >&2
  exit 0
fi

if [[ -n "$OVERLAY_CONFIG_PATH" ]]; then
  export OPENCLAW_CONFIG_PATH="$OVERLAY_CONFIG_PATH"
fi
exec "${cmd[@]}"
