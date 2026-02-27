#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo" >&2
  exit 1
fi

if ! command -v tailscale >/dev/null 2>&1; then
  echo "FAIL: tailscale not installed (tailscale binary missing)" >&2
  exit 1
fi

tailscale serve --http=18789 http://127.0.0.1:18789
tailscale serve status
