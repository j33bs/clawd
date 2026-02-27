#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:18789}"
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

fail=0
paths=(
  "/health"
  "/ready"
  "/diag/runtime"
  "/api/does-not-exist"
  "/diag/does-not-exist"
)

for path in "${paths[@]}"; do
  path_fail=0
  tmp_body="$(mktemp)"
  tmp_headers="$(mktemp)"
  status="$(curl -sS -o "$tmp_body" -D "$tmp_headers" "${curl_headers[@]}" "${BASE_URL}${path}" -w '%{http_code}' || true)"
  ct="$(awk -F': ' 'tolower($1)=="content-type"{print tolower($2)}' "$tmp_headers" | tr -d '\r' | tail -n1)"
  body="$(cat "$tmp_body")"
  rm -f "$tmp_body" "$tmp_headers"

  if [[ -z "$status" || "$status" == "000" ]]; then
    echo "FAIL ${path}: no HTTP response" >&2
    path_fail=1
    fail=1
    continue
  fi
  if [[ "$ct" != *"application/json"* ]]; then
    echo "FAIL ${path}: content-type=${ct:-<missing>} (expected application/json)" >&2
    path_fail=1
    fail=1
  fi
  if grep -Eiq '<!doctype html>|<openclaw-app>' <<<"$body"; then
    echo "FAIL ${path}: html marker detected in body" >&2
    path_fail=1
    fail=1
  fi
  if [[ $path_fail -eq 0 ]]; then
    echo "PASS ${path}: status=${status} content-type=${ct}"
  fi
done

if [[ $fail -ne 0 ]]; then
  echo "reliability tripwire FAILED for ${BASE_URL}" >&2
  exit 1
fi

echo "reliability tripwire passed for ${BASE_URL}"
