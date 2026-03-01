#!/usr/bin/env bash
# inject_gateway_config_overrides.sh — CSA CCM v4 AIS-03, IAM-14
#
# Reads OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS (comma-separated list of
# http(s) origins) and emits a JSON config-override patch to
# $OPENCLAW_CONFIG_OVERRIDE_PATH.  Called by the gateway wrapper before
# launch so that tailnet / LAN deployments never require manual config
# file edits.
#
# Exit codes:
#   0  — patch written (or nothing to patch)
#   1  — validation failure or write error

set -euo pipefail

OVERRIDE_PATH="${OPENCLAW_CONFIG_OVERRIDE_PATH:-}"

if [[ -z "${OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS:-}" ]]; then
  # Nothing to inject; exit cleanly.
  exit 0
fi

if [[ -z "${OVERRIDE_PATH}" ]]; then
  echo "inject_gateway_config_overrides: OPENCLAW_CONFIG_OVERRIDE_PATH must be set when OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS is non-empty" >&2
  exit 1
fi

# Validate that jq is available.
if ! command -v jq >/dev/null 2>&1; then
  echo "inject_gateway_config_overrides: jq is required but not found in PATH" >&2
  exit 1
fi

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

# Parse and validate origins, building a JSON array.
IFS=',' read -r -a raw_origins <<< "${OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS}"
origins_json='[]'

for raw in "${raw_origins[@]}"; do
  origin="$(printf '%s' "${raw}" | xargs)"
  [[ -n "${origin}" ]] || continue

  # Reject wildcards.
  if [[ "${origin}" == *"*"* ]]; then
    echo "inject_gateway_config_overrides: wildcard origin rejected (${origin})" >&2
    exit 1
  fi

  # Must be a valid http(s) URL.
  if [[ ! "${origin}" =~ ^https?://[^[:space:]]+$ ]]; then
    echo "inject_gateway_config_overrides: invalid origin format (${origin})" >&2
    exit 1
  fi

  # Plain http only permitted for loopback hosts.
  if [[ "${origin}" == http://* ]]; then
    host="${origin#http://}"
    host="${host%%/*}"
    if ! is_loopback_host "${host}"; then
      echo "inject_gateway_config_overrides: insecure non-loopback http origin rejected (${origin})" >&2
      exit 1
    fi
  fi

  origins_json="$(jq -n --argjson arr "${origins_json}" --arg v "${origin}" '$arr + [$v]')"
done

# Ensure override directory exists.
override_dir="$(dirname "${OVERRIDE_PATH}")"
mkdir -p "${override_dir}"

# Write JSON patch.
jq -n --argjson origins "${origins_json}" \
  '{"gateway":{"controlUi":{"allowedOrigins": $origins}}}' \
  > "${OVERRIDE_PATH}"

echo "inject_gateway_config_overrides: wrote config override to ${OVERRIDE_PATH} (${#raw_origins[@]} origin(s))"
