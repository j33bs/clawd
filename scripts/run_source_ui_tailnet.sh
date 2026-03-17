#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${OPENCLAW_SOURCE_UI_TAILNET_HOST:-}"
PORT="${OPENCLAW_SOURCE_UI_TAILNET_PORT:-18990}"

if [[ -z "$HOST" ]]; then
  HOST="$(tailscale ip -4 | head -n 1 | tr -d '[:space:]')"
fi

if [[ -z "$HOST" ]]; then
  echo "FATAL: unable to resolve Tailscale IPv4 for Source UI tailnet bind" >&2
  exit 2
fi

pattern="app.py --host ${HOST} --port ${PORT}"
mapfile -t existing_pids < <(pgrep -f "$pattern" || true)

if ((${#existing_pids[@]} > 0)); then
  echo "INFO: stopping existing Source UI instance(s) on ${HOST}:${PORT}: ${existing_pids[*]}" >&2
  kill "${existing_pids[@]}" 2>/dev/null || true

  remaining=("${existing_pids[@]}")
  for _ in {1..20}; do
    next_remaining=()
    for pid in "${remaining[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        next_remaining+=("$pid")
      fi
    done
    if ((${#next_remaining[@]} == 0)); then
      break
    fi
    remaining=("${next_remaining[@]}")
    sleep 0.25
  done

  if ((${#remaining[@]} > 0)); then
    echo "WARN: force-killing stubborn Source UI instance(s): ${remaining[*]}" >&2
    kill -KILL "${remaining[@]}" 2>/dev/null || true
  fi
fi

exec /usr/bin/python3 "$ROOT/workspace/source-ui/app.py" --host "$HOST" --port "$PORT"
