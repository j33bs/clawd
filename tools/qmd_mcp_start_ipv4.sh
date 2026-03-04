#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -n "${NODE_OPTIONS:-}" ]; then
  export NODE_OPTIONS="--dns-result-order=ipv4first ${NODE_OPTIONS}"
else
  export NODE_OPTIONS="--dns-result-order=ipv4first"
fi

qmd mcp stop >/dev/null 2>&1 || true
qmd mcp --http --daemon
sleep 1

if ! lsof -nP -iTCP:8181 -sTCP:LISTEN | grep -q "127.0.0.1:8181 (LISTEN)"; then
  echo "FAIL: qmd mcp is not listening on 127.0.0.1:8181" >&2
  lsof -nP -iTCP:8181 -sTCP:LISTEN >&2 || true
  exit 1
fi

HTTP_CODE="$(curl -sS --max-time 2 -o /dev/null -w "%{http_code}" http://127.0.0.1:8181/mcp || true)"
if [ -z "$HTTP_CODE" ] || [ "$HTTP_CODE" = "000" ]; then
  echo "FAIL: curl could not reach http://127.0.0.1:8181/mcp" >&2
  exit 1
fi

echo "PASS: qmd mcp is reachable on 127.0.0.1:8181/mcp (http_code=$HTTP_CODE)"
