#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${OPENCLAW_SURFACE_BASE_URL:-http://127.0.0.1:18789}}"
AUTH_TOKEN="${OPENCLAW_SURFACE_TOKEN:-}"

if [[ -z "$AUTH_TOKEN" ]]; then
  maybe_token="$(launchctl print "gui/$(id -u)/ai.openclaw.gateway" 2>/dev/null | awk -F'=> ' '/OPENCLAW_GATEWAY_TOKEN/ { gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit }')"
  if [[ -n "$maybe_token" ]]; then
    AUTH_TOKEN="$maybe_token"
  fi
fi

curl_headers=()
if [[ -n "$AUTH_TOKEN" ]]; then
  curl_headers+=(-H "Authorization: Bearer ${AUTH_TOKEN}")
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

probe() {
  local route="$1"
  local expect_status="${2:-}"
  local hdr="$tmpdir/headers_$(echo "$route" | tr '/:' '__')"
  local body="$tmpdir/body_$(echo "$route" | tr '/:' '__')"

  if (( ${#curl_headers[@]} > 0 )); then
    curl -sS -D "$hdr" -o "$body" "${curl_headers[@]}" "${BASE_URL}${route}"
  else
    curl -sS -D "$hdr" -o "$body" "${BASE_URL}${route}"
  fi

  local status
  status="$(awk '/^HTTP\// { code=$2 } END { print code }' "$hdr")"
  local ctype
  ctype="$(awk 'tolower($1)=="content-type:" { line=$0 } END { sub(/\r$/, "", line); sub(/^[^:]*:[[:space:]]*/, "", line); print line }' "$hdr")"

  if [[ "$ctype" =~ [Tt][Ee][Xx][Tt]/[Hh][Tt][Mm][Ll] ]]; then
    echo "FAIL ${route}: machine route returned HTML content-type (${ctype})"
    exit 1
  fi
  if [[ ! "$ctype" =~ [Aa][Pp][Pp][Ll][Ii][Cc][Aa][Tt][Ii][Oo][Nn]/[Jj][Ss][Oo][Nn] ]]; then
    echo "FAIL ${route}: expected JSON content-type, got '${ctype:-<none>}'"
    exit 1
  fi
  if [[ -n "$expect_status" && "$status" != "$expect_status" ]]; then
    echo "FAIL ${route}: expected HTTP ${expect_status}, got ${status}"
    exit 1
  fi

  if grep -Eiq '<!doctype html>|<html' "$body"; then
    echo "FAIL ${route}: response body contained HTML"
    exit 1
  fi

  echo "PASS ${route}: status=${status} content-type=${ctype}"
}

probe "/health"
probe "/ready"
probe "/diag/runtime"
probe "/api/does-not-exist" "404"
probe "/diag/does-not-exist" "404"

echo "machine surface assertion passed for ${BASE_URL}"
