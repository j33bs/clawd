#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "usage: $0 <tailscale-host-or-ip>" >&2
  exit 1
fi

curl -s -o /dev/null -w "%{http_code} %{time_total}\n" "http://$1:18789/health"
